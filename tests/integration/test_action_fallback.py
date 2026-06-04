"""update/delete reuse the read predicate unless a stricter rule is registered.

Post registers its own (stricter) update rule; Comment registers none and so
falls back to its read governance (which, being unruled, is tenant-open)."""

from __future__ import annotations

from conftest import Env
from models import Comment, Post, admin_ctx, author_ctx


async def test_update_uses_its_own_stricter_rule(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        post1 = await s.get(Post, env.ids["post1"])
        assert await env.pv.authorize(s, "update", post1) is True


async def test_admin_may_read_but_not_update_anothers_post(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        post1 = await s.get(Post, env.ids["post1"])  # admin can load it
        assert await env.pv.authorize(s, "read", post1) is True
        assert await env.pv.authorize(s, "update", post1) is False  # not the author


async def test_update_falls_back_to_read_for_an_unruled_model(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        comment = await s.get(Comment, 1)  # org1 comment, no update rule on Comment
        assert await env.pv.authorize(s, "update", comment) is True


async def test_update_denied_cross_tenant_even_when_unruled(env: Env) -> None:
    async with env.unbound() as u:
        planted = await u.get(Comment, env.ids["planted"])  # org2 comment
    async with env.bound(admin_ctx(tenant=1)) as s:
        assert await env.pv.authorize(s, "update", planted) is False
