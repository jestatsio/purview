"""``session.get()`` is safe: it filters on an identity-map miss and respects the
fine-grained read predicate, so no foreign or unauthorised row leaks through it."""

from __future__ import annotations

from conftest import Env
from models import Post, admin_ctx, author_ctx
from sqlalchemy import select


async def test_get_foreign_tenant_returns_none(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        assert await s.get(Post, env.ids["post2"]) is None


async def test_get_same_tenant_returns_row(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        post = await s.get(Post, env.ids["post1"])
        assert post is not None
        assert post.org_id == 1


async def test_get_respects_read_predicate(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        # alice may see her own post but not bob's, even in the same tenant
        assert await s.get(Post, env.ids["post1"]) is not None
        assert await s.get(Post, env.ids["post1b"]) is None


async def test_warm_identity_map_still_filtered(env: Env) -> None:
    # Load a visible row first (warms the map), then probe a foreign one.
    async with env.bound(admin_ctx(tenant=1)) as s:
        await s.scalars(select(Post))
        assert await s.get(Post, env.ids["post2"]) is None
