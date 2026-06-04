"""C1: fine-grained create rules. ``@policy.create_rule`` constrains the proposed
instance; the tenant is validated structurally regardless."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from purview import Context, Policy
from purview.sqlalchemy import Purview, install


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer)
    author_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(50))


def _policy_with_create_rule() -> Policy:
    policy = Policy()

    @policy.create_rule(Post)
    def author_owns(ctx: Context[int, int], post: Post) -> bool:
        return post.author_id == ctx.user_id

    return policy


@asynccontextmanager
async def _installed(
    policy: Policy,
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], Purview]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, policy, tenant_column="tenant_id")
    try:
        yield sm, pv
    finally:
        pv.uninstall()
        await engine.dispose()


async def test_create_rule_allows_matching_author() -> None:
    async with _installed(_policy_with_create_rule()) as (sm, pv), sm() as s:
        pv.bind(s, Context(user_id=7, tenant_id=1))
        assert pv.validate_create(s, Post(author_id=7, title="mine")) is True


async def test_create_rule_rejects_other_author() -> None:
    async with _installed(_policy_with_create_rule()) as (sm, pv), sm() as s:
        pv.bind(s, Context(user_id=7, tenant_id=1))
        assert pv.validate_create(s, Post(author_id=8, title="theirs")) is False


async def test_tenant_is_checked_alongside_the_create_rule() -> None:
    async with _installed(_policy_with_create_rule()) as (sm, pv), sm() as s:
        pv.bind(s, Context(user_id=7, tenant_id=1))
        # correct author but a forged tenant is still refused
        assert pv.validate_create(s, Post(tenant_id=2, author_id=7, title="x")) is False


async def test_no_create_rule_is_tenant_only() -> None:
    async with _installed(Policy()) as (sm, pv), sm() as s:
        pv.bind(s, Context(user_id=7, tenant_id=1))
        assert pv.validate_create(s, Post(author_id=999, title="x")) is True  # author unconstrained
        assert pv.validate_create(s, Post(tenant_id=2, author_id=7, title="x")) is False
