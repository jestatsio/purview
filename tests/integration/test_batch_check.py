"""The batch check answers the object question for many ids in one query."""

from __future__ import annotations

from conftest import Env
from models import Post, admin_ctx, author_ctx


async def test_authorized_ids_returns_only_owned_in_tenant(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        candidates = [env.ids["post1"], env.ids["post1b"], env.ids["post2"]]
        allowed = await env.pv.authorized_ids(s, "read", Post, candidates)
        assert set(allowed) == {env.ids["post1"]}


async def test_authorized_ids_for_admin_returns_all_in_tenant(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        candidates = [env.ids["post1"], env.ids["post1b"], env.ids["post2"]]
        allowed = await env.pv.authorized_ids(s, "read", Post, candidates)
        assert set(allowed) == {env.ids["post1"], env.ids["post1b"]}  # not the org2 post


async def test_authorized_ids_empty_input(env: Env) -> None:
    async with env.bound(admin_ctx(tenant=1)) as s:
        assert await env.pv.authorized_ids(s, "read", Post, []) == []
