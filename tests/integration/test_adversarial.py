"""The adversarial suite — each test is an attacker actively trying to retrieve a
tenant-2 row while authenticated as tenant 1. A passing test means the leak is
*impossible*, not merely unobserved. This is the suite that earns the security
claim; a failure here blocks release regardless of coverage.
"""

from __future__ import annotations

import pytest
from conftest import Env
from models import Comment, Post, admin_ctx, author_ctx, plain_ctx
from sqlalchemy import ForeignKey, Integer, String, select, true
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload
from sqlalchemy.pool import StaticPool

from purview import READ, Context, Policy
from purview.exceptions import CrossTenantWrite
from purview.sqlalchemy import bypass, install


async def test_no_leak_via_session_get(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        assert await s.get(Post, env.ids["post2"]) is None  # org2 row, never served


async def test_no_leak_via_eager_load(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        post = (
            await s.scalars(
                select(Post).where(Post.id == env.ids["post1"]).options(selectinload(Post.comments))
            )
        ).one()
        assert env.ids["planted"] not in {c.id for c in post.comments}  # org2 child hidden


async def test_no_leak_via_lazy_load(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        post = (await s.scalars(select(Post).where(Post.id == env.ids["post1"]))).one()
        comments = await post.awaitable_attrs.comments
        assert env.ids["planted"] not in {c.id for c in comments}


async def test_no_leak_via_top_level_select(env: Env) -> None:
    async with env.bound(plain_ctx(tenant=1)) as s:
        comments = (await s.scalars(select(Comment))).all()
        assert all(c.org_id == 1 for c in comments)


async def test_enforcement_resumes_after_bypass_exits(env: Env) -> None:
    async with env.bound(plain_ctx(tenant=1)) as s:
        with bypass(reason="adversarial check"):
            assert len((await s.scalars(select(Post))).all()) == 3  # all tenants, briefly
        assert (await s.scalars(select(Post))).all() == []  # locked down again


async def test_no_leak_via_forged_create(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        s.add(Post(id=500, org_id=2, author_id=env.ids["alice"], title="forged"))
        with pytest.raises(CrossTenantWrite):
            await s.commit()


async def test_no_leak_via_cross_tenant_update(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        post1 = await s.get(Post, env.ids["post1"])
        assert post1 is not None
        post1.org_id = 2
        with pytest.raises(CrossTenantWrite):
            await s.commit()


async def test_no_leak_via_relationship_join_predicate() -> None:
    """A policy whose rule traverses a relationship must not let a check or filter
    leak across the tenant: the join is evaluated inside the tenant scope."""

    class Base(DeclarativeBase):
        pass

    class Author(Base):
        __tablename__ = "adv_author"
        id: Mapped[int] = mapped_column(primary_key=True)
        org_id: Mapped[int] = mapped_column(Integer)
        verified: Mapped[bool] = mapped_column()

    class Article(Base):
        __tablename__ = "adv_article"
        id: Mapped[int] = mapped_column(primary_key=True)
        org_id: Mapped[int] = mapped_column(Integer)
        author_id: Mapped[int] = mapped_column(ForeignKey("adv_author.id"))
        title: Mapped[str] = mapped_column(String(50))
        author: Mapped[Author] = relationship()

    policy = Policy()

    @policy.rule(Article, READ)
    def read_article(ctx: Context[int, int]) -> list:
        # visible only if the article's author is verified (a join predicate)
        return [Article.author.has(Author.verified == true())]

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, policy, tenant_column="org_id")
    try:
        async with sm() as s:  # unbound seed
            s.add_all(
                [
                    Author(id=1, org_id=1, verified=True),
                    Author(id=2, org_id=2, verified=True),
                    Article(id=1, org_id=1, author_id=1, title="t1"),
                    Article(id=2, org_id=2, author_id=2, title="t2"),  # org2, verified author
                ]
            )
            await s.commit()

        ctx: Context[int, int] = Context(1, 1, frozenset())
        async with sm() as s:
            pv.bind(s, ctx)
            # filter form: the join predicate is satisfied, but tenant scope wins
            visible = (await s.scalars(select(Article))).all()
            assert {a.id for a in visible} == {1}
            # check form: cannot authorize a tenant-2 article from a tenant-1 session
            async with sm() as u:
                org2_article = await u.get(Article, 2)
            assert await pv.authorize(s, "read", org2_article) is False
    finally:
        pv.uninstall()
        await engine.dispose()
