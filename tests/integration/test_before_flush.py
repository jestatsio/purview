"""The write guard closes the write path: auto-populate tenant, reject forged
inserts, reject cross-tenant moves."""

from __future__ import annotations

import pytest
from conftest import Env
from models import Post, author_ctx

from purview.exceptions import CrossTenantWrite


async def test_insert_auto_populates_tenant(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        s.add(Post(id=200, author_id=env.ids["alice"], title="new"))  # no org_id
        await s.commit()
        row = await s.get(Post, 200)
        assert row is not None
        assert row.org_id == 1


async def test_forged_tenant_insert_is_rejected(env: Env) -> None:
    # Forge the tenant *after* attach (attach saw no tenant) so the flush-time
    # write guard is what rejects it.
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        post = Post(id=201, author_id=env.ids["alice"], title="forged")
        s.add(post)
        post.org_id = 2
        with pytest.raises(CrossTenantWrite):
            await s.commit()


async def test_cross_tenant_move_is_rejected(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        post1 = await s.get(Post, env.ids["post1"])
        assert post1 is not None
        post1.org_id = 2
        with pytest.raises(CrossTenantWrite):
            await s.commit()
