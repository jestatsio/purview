"""Adversarial coverage for ORM paths that could sidestep the read/write guards:
merge, refresh, detached re-attach, single-table inheritance, the rebind guard,
and the documented raw-SQL / lazy-load boundary. Each test is an attacker."""

from __future__ import annotations

import pytest
from conftest import Env
from models import Post, admin_ctx, author_ctx, plain_ctx
from sqlalchemy import Integer, String, select, text
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from purview import Context, Policy
from purview.exceptions import CrossTenantWrite, TenantMismatch
from purview.sqlalchemy import install


# -- A1: session.merge() ----------------------------------------------------- #
async def test_no_leak_via_merge(env: Env) -> None:
    # Obtain a detached org-2 object, then try to merge it into a tenant-1 session.
    async with env.unbound() as u:
        post2 = await u.get(Post, env.ids["post2"])
        assert post2 is not None
        u.expunge(post2)
    async with env.bound(author_ctx(tenant=1)) as s:
        # merge's load is tenant-scoped (finds nothing), so it builds a pending org-2
        # row; the write guard refuses it at flush.
        await s.merge(post2)
        with pytest.raises(CrossTenantWrite):
            await s.commit()


# -- A2: refresh / populate_existing ----------------------------------------- #
async def test_refresh_and_populate_existing_stay_scoped(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        post1 = await s.get(Post, env.ids["post1"])
        assert post1 is not None
        await s.refresh(post1)
        assert post1.org_id == 1
        # a populate_existing reload does not pull a foreign row into the map
        await s.scalars(select(Post).execution_options(populate_existing=True))
        assert await s.get(Post, env.ids["post2"]) is None


# -- A3: detached object re-attached into another tenant's session ----------- #
async def test_no_leak_via_detached_reattach(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s1:
        post1 = await s1.get(Post, env.ids["post1"])  # org 1
        assert post1 is not None
        s1.expunge(post1)
    async with env.bound(plain_ctx(tenant=2)) as s2:
        with pytest.raises(CrossTenantWrite):
            s2.add(post1)  # the attach guard refuses an org-1 object entering tenant 2


# -- A6: rebinding a session to a different tenant --------------------------- #
async def test_rebind_to_different_tenant_raises(env: Env) -> None:
    async with env.sessionmaker() as s:
        env.pv.bind(s, plain_ctx(tenant=1))
        with pytest.raises(TenantMismatch):
            env.pv.bind(s, plain_ctx(tenant=2))


async def test_rebind_within_same_tenant_is_allowed(env: Env) -> None:
    async with env.sessionmaker() as s:
        env.pv.bind(s, author_ctx(user_id=1, tenant=1))
        env.pv.bind(s, author_ctx(user_id=2, tenant=1))  # same tenant, different user


# -- A7: documented boundary — raw SQL is NOT filtered, lazy raises ---------- #
async def test_raw_text_sql_is_not_filtered(env: Env) -> None:
    # The sharp edge: raw SQL is outside the enforcement boundary, by design.
    async with env.bound(plain_ctx(tenant=1)) as s:
        rows = (await s.execute(text("SELECT org_id FROM post"))).all()
        assert {r[0] for r in rows} == {1, 2}  # sees every tenant


async def test_implicit_lazy_load_raises_rather_than_leaking(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        post1 = (await s.scalars(select(Post).where(Post.id == env.ids["post1"]))).one()
        with pytest.raises(MissingGreenlet):
            _ = post1.comments  # implicit sync lazy load under async — fails loud, no leak


# -- A5: single-table inheritance (self-contained) --------------------------- #
async def test_single_table_inheritance_is_tenant_filtered() -> None:
    class Base(DeclarativeBase):
        pass

    class Vehicle(Base):
        __tablename__ = "sti_vehicle"
        id: Mapped[int] = mapped_column(primary_key=True)
        org_id: Mapped[int] = mapped_column(Integer)
        kind: Mapped[str] = mapped_column(String(20))
        name: Mapped[str] = mapped_column(String(50))
        __mapper_args__ = {"polymorphic_on": "kind", "polymorphic_identity": "vehicle"}

    class Car(Vehicle):  # single-table: no __tablename__, shares sti_vehicle
        wheels: Mapped[int | None] = mapped_column(default=None)
        __mapper_args__ = {"polymorphic_identity": "car"}

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, Policy(), tenant_column="org_id")
    try:
        async with sm() as s:  # unbound seed
            s.add_all(
                [
                    Car(id=1, org_id=1, kind="car", name="org1-car", wheels=4),
                    Car(id=2, org_id=2, kind="car", name="org2-car", wheels=4),
                ]
            )
            await s.commit()
        async with sm() as s:
            pv.bind(s, Context(1, 1, frozenset()))
            cars = (await s.scalars(select(Car))).all()
            vehicles = (await s.scalars(select(Vehicle))).all()
            assert {c.id for c in cars} == {1}  # subclass select is tenant-filtered
            assert {v.id for v in vehicles} == {1}  # base select too
    finally:
        pv.uninstall()
        await engine.dispose()
