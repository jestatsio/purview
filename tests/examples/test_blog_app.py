"""End-to-end dogfood: a small FastAPI + SQLAlchemy blog wired with Purview,
driven over real HTTP. This file is also the worked example of idiomatic usage.

It demonstrates the whole stack from one policy definition:
  * collection reads filter automatically (tenant + role),
  * object reads 404 across the tenant boundary,
  * object updates 403 when the actor may read but not act,
  * creates are tenant-stamped, and forged-tenant creates are refused.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import ForeignKey, Integer, String, select, true
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from purview import READ, Context, Policy
from purview.fastapi import authorize_or_403, context_binder, install_error_handlers, requires
from purview.sqlalchemy import Purview, install


# --- the app's own models (Purview owns no schema) --------------------------- #
class Base(AsyncAttrs, DeclarativeBase):
    pass


class Org(Base):
    __tablename__ = "org"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class Membership(Base):  # role assignments are DATA, in the app's tables
    __tablename__ = "membership"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer)
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    title: Mapped[str] = mapped_column(String(120))


# --- the policy (CODE): row-shaping logic, type-checked and testable --------- #
def build_policy() -> Policy:
    policy = Policy()
    policy.global_model(Org)
    policy.global_model(User)

    @policy.rule(Post, READ)
    def read_post(ctx: Context[int, int]) -> list:
        rules = []
        if ctx.has_role("author"):
            rules.append(Post.author_id == ctx.user_id)
        if ctx.has_role("org_admin"):
            rules.append(true())
        return rules

    @policy.rule(Post, "update")
    def update_post(ctx: Context[int, int]) -> list:
        return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []

    return policy


async def _seed(sm: async_sessionmaker[AsyncSession]) -> None:
    async with sm() as s:  # unbound bootstrap
        s.add_all(
            [
                Org(id=1, name="Acme"),
                Org(id=2, name="Globex"),
                User(id=1, name="alice"),
                User(id=2, name="bob"),
                User(id=3, name="carol"),
                User(id=4, name="dave"),
                User(id=5, name="eve"),
                Membership(id=1, org_id=1, user_id=1, role="author"),
                Membership(id=2, org_id=1, user_id=2, role="author"),
                Membership(id=3, org_id=2, user_id=3, role="author"),
                Membership(id=4, org_id=1, user_id=4, role="org_admin"),
                Membership(id=5, org_id=1, user_id=5, role="guest"),  # no Post grant
                Post(id=1, org_id=1, author_id=1, title="alice-post"),
                Post(id=2, org_id=1, author_id=2, title="bob-post"),
                Post(id=3, org_id=2, author_id=3, title="carol-post"),
            ]
        )
        await s.commit()


async def create_app() -> tuple[FastAPI, Purview]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, build_policy(), tenant_column="org_id")
    await _seed(sm)

    app = FastAPI()
    install_error_handlers(app)

    async def get_session() -> AsyncIterator[AsyncSession]:
        async with sm() as session:
            yield session

    async def get_context(
        x_user_id: int = Header(),
        x_org_id: int = Header(),
    ) -> Context[int, int]:
        # The auth bootstrap: load the actor's roles for this tenant (unbound).
        async with sm() as session:
            roles = set(
                await session.scalars(
                    select(Membership.role).where(
                        Membership.user_id == x_user_id,
                        Membership.org_id == x_org_id,
                    )
                )
            )
        if not roles:
            raise HTTPException(status_code=401, detail="no membership in this org")
        return Context(user_id=x_user_id, tenant_id=x_org_id, roles=frozenset(roles))

    bound = context_binder(pv, get_session, get_context)

    @app.get("/posts")
    async def list_posts(session: AsyncSession = Depends(bound)) -> list[dict[str, Any]]:
        posts = (await session.scalars(select(Post))).all()
        return [{"id": p.id, "title": p.title} for p in posts]

    @app.get("/posts/{post_id}")
    async def get_post(post_id: int, session: AsyncSession = Depends(bound)) -> dict[str, Any]:
        post = await session.get(Post, post_id)  # auto-filtered: invisible → None
        if post is None:
            raise HTTPException(status_code=404, detail="not found")
        return {"id": post.id, "title": post.title}

    @app.post("/posts", status_code=201)
    async def create_post(
        payload: dict[str, Any],
        session: AsyncSession = Depends(bound),
    ) -> dict[str, Any]:
        ctx = pv.context(session)
        post = Post(title=payload["title"], author_id=ctx.user_id)
        if "org_id" in payload:  # let a client try to forge the tenant
            post.org_id = payload["org_id"]
        session.add(post)
        await session.commit()  # write guard stamps / rejects here
        return {"id": post.id, "org_id": post.org_id}

    @app.patch("/posts/{post_id}")
    async def update_post(
        post_id: int,
        payload: dict[str, Any],
        session: AsyncSession = Depends(bound),
    ) -> dict[str, Any]:
        post = await session.get(Post, post_id)
        if post is None:
            raise HTTPException(status_code=404, detail="not found")
        await authorize_or_403(pv, session, "update", post)  # 403 if not the author
        post.title = payload["title"]
        await session.commit()
        return {"id": post.id, "title": post.title}

    @app.get("/guarded-posts", dependencies=[Depends(requires(pv, READ, Post, get_context))])
    async def guarded_posts(session: AsyncSession = Depends(bound)) -> list[dict[str, Any]]:
        # The route guard 403s an actor with no standing grant before we query.
        return [{"id": p.id} for p in (await session.scalars(select(Post))).all()]

    return app, pv


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app, pv = await create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    pv.uninstall()


def _as(user_id: int, org_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id), "X-Org-Id": str(org_id)}


async def test_author_lists_only_own_posts(client: AsyncClient) -> None:
    resp = await client.get("/posts", headers=_as(1, 1))  # alice, org1
    assert resp.status_code == 200
    assert {p["title"] for p in resp.json()} == {"alice-post"}


async def test_org_admin_lists_all_in_tenant(client: AsyncClient) -> None:
    resp = await client.get("/posts", headers=_as(4, 1))  # dave, org1 admin
    assert {p["title"] for p in resp.json()} == {"alice-post", "bob-post"}


async def test_other_tenant_is_isolated(client: AsyncClient) -> None:
    resp = await client.get("/posts", headers=_as(3, 2))  # carol, org2
    assert {p["title"] for p in resp.json()} == {"carol-post"}


async def test_cross_tenant_object_read_is_404(client: AsyncClient) -> None:
    resp = await client.get("/posts/3", headers=_as(1, 1))  # alice -> org2 post
    assert resp.status_code == 404


async def test_admin_may_read_but_not_update_anothers_post(client: AsyncClient) -> None:
    assert (await client.get("/posts/2", headers=_as(4, 1))).status_code == 200  # readable
    resp = await client.patch("/posts/2", headers=_as(4, 1), json={"title": "hijacked"})
    assert resp.status_code == 403  # but not updatable by the admin


async def test_author_updates_own_post(client: AsyncClient) -> None:
    resp = await client.patch("/posts/2", headers=_as(2, 1), json={"title": "bob-edit"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "bob-edit"


async def test_create_is_tenant_stamped(client: AsyncClient) -> None:
    resp = await client.post("/posts", headers=_as(1, 1), json={"title": "fresh"})
    assert resp.status_code == 201
    assert resp.json()["org_id"] == 1


async def test_forged_tenant_create_is_refused(client: AsyncClient) -> None:
    resp = await client.post("/posts", headers=_as(1, 1), json={"title": "x", "org_id": 2})
    assert resp.status_code == 403


async def test_route_guard_403s_actor_with_no_grant(client: AsyncClient) -> None:
    assert (await client.get("/guarded-posts", headers=_as(5, 1))).status_code == 403  # eve, guest


async def test_route_guard_admits_actor_with_a_grant(client: AsyncClient) -> None:
    assert (await client.get("/guarded-posts", headers=_as(1, 1))).status_code == 200  # alice
