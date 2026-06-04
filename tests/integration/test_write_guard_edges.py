"""Write-guard branches that matter for the write path: bypass, global models,
and ordinary in-tenant updates."""

from __future__ import annotations

from conftest import Env
from models import GlobalThing, Post, author_ctx

from purview.sqlalchemy import bypass


async def test_bypass_allows_a_cross_tenant_write(env: Env) -> None:
    async with env.bound(author_ctx(tenant=1)) as s:
        with bypass(reason="admin data migration"):
            s.add(Post(id=210, org_id=2, author_id=1, title="cross"))
            await s.commit()
    async with env.unbound() as u:
        row = await u.get(Post, 210)
        assert row is not None
        assert row.org_id == 2  # persisted into org2 under bypass


async def test_global_model_write_is_not_tenant_stamped(env: Env) -> None:
    async with env.bound(author_ctx(tenant=1)) as s:
        s.add(GlobalThing(id=2, label="new-reference"))  # no tenant column
        await s.commit()
        row = await s.get(GlobalThing, 2)
        assert row is not None


async def test_updating_a_non_tenant_field_is_allowed(env: Env) -> None:
    async with env.bound(author_ctx(user_id=env.ids["alice"], tenant=1)) as s:
        post1 = await s.get(Post, env.ids["post1"])
        assert post1 is not None
        post1.title = "renamed"
        await s.commit()  # tenant unchanged → no rejection
        refreshed = await s.get(Post, env.ids["post1"])
        assert refreshed is not None
        assert refreshed.title == "renamed"
