"""Collection reads filter automatically on a bound session: tenant scope always,
plus the read predicate for models that have one."""

from __future__ import annotations

from conftest import Env
from models import Comment, Post, admin_ctx, author_ctx, plain_ctx
from sqlalchemy import select


async def test_tenant_scopes_every_collection(env: Env) -> None:
    async with env.bound(author_ctx(tenant=1)) as s:
        posts = (await s.scalars(select(Post))).all()
        assert {p.org_id for p in posts} <= {1}


async def test_author_sees_only_own_posts(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        posts = (await s.scalars(select(Post))).all()
        assert {p.id for p in posts} == {env.ids["post1"]}


async def test_org_admin_sees_all_in_tenant_posts(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        posts = (await s.scalars(select(Post))).all()
        assert {p.id for p in posts} == {env.ids["post1"], env.ids["post1b"]}


async def test_no_granting_role_denies_a_ruled_model(env: Env) -> None:
    async with env.bound(plain_ctx(tenant=1)) as s:
        posts = (await s.scalars(select(Post))).all()
        assert posts == []


async def test_unruled_model_is_tenant_scope_only(env: Env) -> None:
    async with env.bound(plain_ctx(tenant=1)) as s:
        comments = (await s.scalars(select(Comment))).all()
        assert {c.org_id for c in comments} == {1}
        assert env.ids["planted"] not in {c.id for c in comments}
