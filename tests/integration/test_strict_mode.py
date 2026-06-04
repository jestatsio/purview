"""strict=True flips the within-tenant default: a scoped model with no read rule
denies instead of being tenant-scope-only. The cross-tenant boundary is enforced
identically either way; strict only governs unruled models within a tenant."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from models import Base, Comment, GlobalThing, Org, Post, User, build_policy
from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from purview import READ, Context, Policy
from purview.sqlalchemy import Purview, install


def _base_policy() -> Policy:
    policy = Policy()
    policy.global_model(Org)
    policy.global_model(GlobalThing)
    return policy


@asynccontextmanager
async def _env(
    policy: Policy, *, strict: bool
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], Purview]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, policy, tenant_column="org_id", strict=strict)
    async with sm() as s:
        s.add_all(
            [
                Org(id=1, name="Acme"),
                User(id=1, org_id=1, name="alice"),
                Post(id=1, org_id=1, author_id=1, title="p"),
                Comment(id=1, org_id=1, post_id=1, body="c"),
            ]
        )
        await s.commit()
    try:
        yield sm, pv
    finally:
        pv.uninstall()
        await engine.dispose()


async def test_strict_denies_an_unruled_model_but_ruled_models_still_work() -> None:
    async with _env(build_policy(), strict=True) as (sm, pv), sm() as s:
        pv.bind(s, Context(1, 1, frozenset({"author"})))
        assert {p.id for p in (await s.scalars(select(Post))).all()} == {1}  # ruled, granted
        assert (await s.scalars(select(Comment))).all() == []  # unruled → denied


async def test_non_strict_leaves_an_unruled_model_tenant_visible() -> None:
    async with _env(build_policy(), strict=False) as (sm, pv), sm() as s:
        pv.bind(s, Context(1, 1, frozenset()))
        assert {c.id for c in (await s.scalars(select(Comment))).all()} == {1}


async def test_strict_grants_when_an_explicit_rule_is_registered() -> None:
    policy = _base_policy()

    @policy.rule(Comment, READ)
    def read_comment(ctx: Context[int, int]) -> list:
        return [true()]  # explicit tenant-wide grant

    async with _env(policy, strict=True) as (sm, pv), sm() as s:
        pv.bind(s, Context(1, 1, frozenset()))
        assert {c.id for c in (await s.scalars(select(Comment))).all()} == {1}


async def test_strict_object_check_denies_unruled_model() -> None:
    async with _env(build_policy(), strict=True) as (sm, pv):
        async with sm() as u:  # unbound load to obtain the object
            comment = await u.get(Comment, 1)
        async with sm() as s:
            pv.bind(s, Context(1, 1, frozenset()))
            assert await pv.authorize(s, "read", comment) is False
