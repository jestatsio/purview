"""B1: per-model tenant column. A model registered via ``set_tenant_field`` is
scoped by its own column, alongside models using the install default — across the
read guard, get, the write/attach guards, and the object check."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from purview import Context, Policy
from purview.exceptions import CrossTenantWrite, UnscopedModel
from purview.sqlalchemy import Purview, install


class Base(DeclarativeBase):
    pass


class Project(Base):  # scoped by a CUSTOM column: account_id
    __tablename__ = "project"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(50))


class Note(Base):  # scoped by the DEFAULT column: tenant_id
    __tablename__ = "note"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(String(50))


@asynccontextmanager
async def _env() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], Purview]]:
    policy = Policy()
    policy.set_tenant_field(Project, "account_id")  # Project overrides; Note uses default
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, policy, tenant_column="tenant_id")
    async with sm() as s:  # unbound seed
        s.add_all(
            [
                Project(id=1, account_id=1, name="p1"),
                Project(id=2, account_id=2, name="p2"),
                Note(id=1, tenant_id=1, body="n1"),
                Note(id=2, tenant_id=2, body="n2"),
            ]
        )
        await s.commit()
    try:
        yield sm, pv
    finally:
        pv.uninstall()
        await engine.dispose()


async def test_each_model_is_filtered_by_its_own_column() -> None:
    async with _env() as (sm, pv), sm() as s:
        pv.bind(s, Context(1, 1, frozenset()))
        assert {p.id for p in await s.scalars(select(Project))} == {1}  # account_id == 1
        assert {n.id for n in await s.scalars(select(Note))} == {1}  # tenant_id == 1


async def test_get_is_scoped_by_the_custom_column() -> None:
    async with _env() as (sm, pv), sm() as s:
        pv.bind(s, Context(1, 1, frozenset()))
        assert await s.get(Project, 2) is None  # account 2 invisible
        assert await s.get(Project, 1) is not None


async def test_write_auto_stamps_and_rejects_on_the_custom_column() -> None:
    async with _env() as (sm, pv):
        async with sm() as s:
            pv.bind(s, Context(1, 1, frozenset()))
            s.add(Project(id=10, name="new"))  # no account_id → stamped
            await s.commit()
            row = await s.get(Project, 10)
            assert row is not None
            assert row.account_id == 1
        async with sm() as s:
            pv.bind(s, Context(1, 1, frozenset()))
            with pytest.raises(CrossTenantWrite):
                s.add(Project(id=11, account_id=2, name="forged"))  # attach guard refuses


async def test_object_check_uses_the_custom_column() -> None:
    async with _env() as (sm, pv):
        async with sm() as u:
            p2 = await u.get(Project, 2)  # unbound load of an account-2 project
        async with sm() as s:
            pv.bind(s, Context(1, 1, frozenset()))
            assert await pv.authorize(s, "read", p2) is False  # cross-account


async def test_unscoped_model_reports_the_expected_default_column() -> None:
    class OtherBase(DeclarativeBase):
        pass

    class Widget(OtherBase):  # has account_id but isn't registered → default applies
        __tablename__ = "widget"
        id: Mapped[int] = mapped_column(primary_key=True)
        account_id: Mapped[int] = mapped_column(Integer)

    with pytest.raises(UnscopedModel, match="tenant_id"):
        install(OtherBase, Policy(), tenant_column="tenant_id")
