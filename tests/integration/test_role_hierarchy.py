"""A declared role implication is expanded at bind, so a higher role transparently
satisfies a rule written against the implied role — across reads, checks, and explain."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from models import Base, Org, Post, User, build_policy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from purview import READ, Context, Policy
from purview.sqlalchemy import Purview, install


def _policy() -> Policy:
    # The standard policy already grants authors their own posts; add an implication
    # so a "manager" is also an "author".
    policy = build_policy()
    policy.role_implies("manager", "author")
    return policy


@asynccontextmanager
async def _env() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], Purview]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, _policy(), tenant_column="org_id")
    async with sm() as s:
        s.add_all(
            [
                Org(id=1, name="Acme"),
                User(id=1, org_id=1, name="alice"),
                User(id=2, org_id=1, name="bob"),
                Post(id=1, org_id=1, author_id=1, title="mine"),
                Post(id=2, org_id=1, author_id=2, title="theirs"),
            ]
        )
        await s.commit()
    try:
        yield sm, pv
    finally:
        pv.uninstall()
        await engine.dispose()


async def test_implied_role_filters_reads() -> None:
    async with _env() as (sm, pv), sm() as s:
        pv.bind(s, Context(1, 1, frozenset({"manager"})))  # only "manager"
        rows = {p.id for p in (await s.scalars(select(Post))).all()}
    assert rows == {1}  # behaves as an author of post 1


async def test_implied_role_satisfies_object_check() -> None:
    async with _env() as (sm, pv):
        async with sm() as u:
            mine = await u.get(Post, 1)
            theirs = await u.get(Post, 2)
        async with sm() as s:
            pv.bind(s, Context(1, 1, frozenset({"manager"})))
            assert await pv.authorize(s, "read", mine) is True
            assert await pv.authorize(s, "read", theirs) is False


async def test_explain_reflects_expanded_roles() -> None:
    async with _env() as (_sm, pv):
        exp = pv.explain(Context(1, 1, frozenset({"manager"})), READ, Post)
    assert {"manager", "author"} <= exp.active_roles
    assert "author_id = 1" in exp.row_sql


async def test_without_the_implied_role_default_deny() -> None:
    async with _env() as (sm, pv), sm() as s:
        pv.bind(s, Context(1, 1, frozenset({"guest"})))  # no path to author
        assert (await s.scalars(select(Post))).all() == []
