"""Tenant criteria must reach relationship loads — eager and lazy — so a planted
cross-tenant child is never returned. This is the load-bearing propagation test."""

from __future__ import annotations

from conftest import Env
from models import Post, admin_ctx
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def test_eager_selectinload_is_tenant_filtered(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        post = (
            await s.scalars(
                select(Post).where(Post.id == env.ids["post1"]).options(selectinload(Post.comments))
            )
        ).one()
        ids = {c.id for c in post.comments}
        assert env.ids["planted"] not in ids
        assert all(c.org_id == 1 for c in post.comments)
        assert ids == {1, 2}


async def test_lazy_awaitable_attrs_is_tenant_filtered(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        post = (await s.scalars(select(Post).where(Post.id == env.ids["post1"]))).one()
        comments = await post.awaitable_attrs.comments
        assert env.ids["planted"] not in {c.id for c in comments}
        assert all(c.org_id == 1 for c in comments)
