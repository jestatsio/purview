"""B2/B3: real-schema id shapes — composite primary keys and UUID/non-int ids."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import Integer, String, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool, StaticPool

from purview import Context, Policy
from purview.exceptions import CrossTenantWrite
from purview.sqlalchemy import Purview, install


def _backends() -> list[str]:
    urls = ["sqlite+aiosqlite:///:memory:"]
    pg = os.environ.get("PURVIEW_TEST_POSTGRES_URL")
    if pg:
        urls.append(pg)
    return urls


_BACKEND_IDS = ["postgres" if "postgres" in u else "sqlite" for u in _backends()]


@asynccontextmanager
async def _installed(
    base: type[DeclarativeBase], policy: Policy, tenant_column: str, url: str
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], Purview]]:
    if url.startswith("sqlite"):
        engine = create_async_engine(
            url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    else:
        engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(base.metadata.drop_all)
        await conn.run_sync(base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(base, policy, tenant_column=tenant_column)
    try:
        yield sm, pv
    finally:
        pv.uninstall()
        await engine.dispose()


# -- B2: composite primary key ----------------------------------------------- #
@pytest.mark.parametrize("url", _backends(), ids=_BACKEND_IDS)
async def test_composite_primary_key_batch_and_object_check(url: str) -> None:
    class Base(DeclarativeBase):
        pass

    class Membership(Base):  # composite PK (org_id, user_id); tenant column = org_id
        __tablename__ = "membership"
        org_id: Mapped[int] = mapped_column(Integer, primary_key=True)
        user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
        role: Mapped[str] = mapped_column(String(20))

    async with _installed(Base, Policy(), "org_id", url) as (sm, pv):
        async with sm() as s:  # unbound seed
            s.add_all(
                [
                    Membership(org_id=1, user_id=1, role="admin"),
                    Membership(org_id=1, user_id=2, role="member"),
                    Membership(org_id=2, user_id=1, role="admin"),
                ]
            )
            await s.commit()

        async with sm() as s:
            pv.bind(s, Context(1, 1, frozenset()))
            # batch check over composite ids returns the in-tenant subset, as tuples
            allowed = await pv.authorized_ids(
                s, "read", Membership, [(1, 1), (1, 2), (2, 1)]
            )
            assert set(allowed) == {(1, 1), (1, 2)}
            # collection + get are tenant-filtered
            assert {(m.org_id, m.user_id) for m in await s.scalars(select(Membership))} == {
                (1, 1),
                (1, 2),
            }
            assert await s.get(Membership, (2, 1)) is None

        # object check on a composite-PK row from another tenant
        async with sm() as u:
            foreign = await u.get(Membership, (2, 1))
        async with sm() as s:
            pv.bind(s, Context(1, 1, frozenset()))
            assert await pv.authorize(s, "read", foreign) is False


# -- B3: UUID ids ------------------------------------------------------------ #
@pytest.mark.parametrize("url", _backends(), ids=_BACKEND_IDS)
async def test_uuid_tenant_and_user_ids(url: str) -> None:
    t1, t2 = uuid.UUID(int=1), uuid.UUID(int=2)

    class Base(DeclarativeBase):
        pass

    class Document(Base):
        __tablename__ = "document"
        id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
        tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid)
        title: Mapped[str] = mapped_column(String(50))

    async with _installed(Base, Policy(), "tenant_id", url) as (sm, pv):
        d1, d2 = uuid.UUID(int=11), uuid.UUID(int=22)
        async with sm() as s:
            s.add_all(
                [
                    Document(id=d1, tenant_id=t1, title="doc1"),
                    Document(id=d2, tenant_id=t2, title="doc2"),
                ]
            )
            await s.commit()

        async with sm() as s:
            pv.bind(s, Context(user_id=uuid.UUID(int=99), tenant_id=t1))
            assert {d.id for d in await s.scalars(select(Document))} == {d1}
            assert await s.get(Document, d2) is None  # other tenant invisible

            new_id = uuid.UUID(int=33)
            s.add(Document(id=new_id, title="new"))  # no tenant → stamped
            await s.commit()
            stamped = await s.get(Document, new_id)
            assert stamped is not None
            assert stamped.tenant_id == t1

            with pytest.raises(CrossTenantWrite):
                s.add(Document(id=uuid.UUID(int=44), tenant_id=t2, title="forged"))
