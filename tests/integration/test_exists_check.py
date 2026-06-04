"""The object-level check (``Purview.authorize``) shares the one policy: it is the
filter predicate scoped to a single row via EXISTS."""

from __future__ import annotations

import pytest
from conftest import Env
from models import Post, admin_ctx, author_ctx

from purview import PurviewError


async def test_authorize_read_true_for_own_post(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        post1 = await s.get(Post, env.ids["post1"])
        assert await env.pv.authorize(s, "read", post1) is True


async def test_authorize_read_false_for_other_users_post(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as a:
        post1b = await a.get(Post, env.ids["post1b"])  # admin can load bob's post
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        assert await env.pv.authorize(s, "read", post1b) is False


async def test_authorize_read_false_cross_tenant(env: Env) -> None:
    async with env.unbound() as u:
        post2 = await u.get(Post, env.ids["post2"])  # unbound load of an org2 row
    async with env.bound(admin_ctx(tenant=1)) as s:
        assert await env.pv.authorize(s, "read", post2) is False


async def test_authorize_requires_bound_session(env: Env) -> None:
    async with env.unbound() as s:
        post1 = await s.get(Post, env.ids["post1"])
        with pytest.raises(PurviewError):
            await env.pv.authorize(s, "read", post1)
