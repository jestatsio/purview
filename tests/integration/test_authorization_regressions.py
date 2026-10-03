"""Authorization helpers preserve the same boundary as automatic ORM reads."""

from __future__ import annotations

import pytest
from conftest import Env
from models import Animal, Dog, GlobalThing, Post, admin_ctx, author_ctx
from sqlalchemy import event, select, true

from purview import READ, Context
from purview.exceptions import CrossTenantWrite, PurviewForbidden
from purview.fastapi import requires
from purview.sqlalchemy import authorized_select


@pytest.mark.parametrize("batch", [False, True])
async def test_check_autoflush_rejects_forged_tenant_insert(env: Env, batch: bool) -> None:
    async with env.bound(author_ctx()) as session:
        target = await session.get(Post, env.ids["post1"])
        assert target is not None
        forged = Post(id=200, author_id=env.ids["alice"], title="forged")
        session.add(forged)
        forged.org_id = 2
        with pytest.raises(CrossTenantWrite):
            if batch:
                await env.pv.authorized_ids(session, READ, Post, [target.id])
            else:
                await env.pv.authorize(session, READ, target)
        await session.rollback()
    async with env.unbound() as session:
        assert await session.get(Post, 200) is None


@pytest.mark.parametrize("batch", [False, True])
async def test_check_autoflush_stamps_valid_insert(env: Env, batch: bool) -> None:
    async with env.bound(author_ctx()) as session:
        target = await session.get(Post, env.ids["post1"])
        assert target is not None
        pending = Post(id=200, author_id=env.ids["alice"], title="new")
        session.add(pending)
        if batch:
            assert await env.pv.authorized_ids(session, READ, Post, [target.id]) == [target.id]
        else:
            assert await env.pv.authorize(session, READ, target)
        await session.commit()
        assert pending.org_id == 1


@pytest.mark.parametrize("batch", [False, True])
async def test_check_autoflush_rejects_cross_tenant_move(env: Env, batch: bool) -> None:
    async with env.bound(author_ctx()) as session:
        target = await session.get(Post, env.ids["post1"])
        assert target is not None
        target.org_id = 2
        with pytest.raises(CrossTenantWrite):
            if batch:
                await env.pv.authorized_ids(session, READ, Post, [target.id])
            else:
                await env.pv.authorize(session, READ, target)


async def test_route_guard_and_explicit_select_expand_implied_roles(env: Env) -> None:
    env.pv.policy.role_implies("manager", "author")
    context = Context(env.ids["alice"], 1, frozenset({"manager"}))
    guard = requires(env.pv, READ, Post, lambda: context)
    await guard(context)
    with pytest.raises(PurviewForbidden):
        await guard(Context(env.ids["alice"], 1))
    async with env.unbound() as session:
        stmt = authorized_select(env.pv.policy, context, Post, "org_id")
        assert [row.id for row in await session.scalars(stmt)] == [env.ids["post1"]]


async def test_global_helpers_apply_rules_without_tenant_column(env: Env) -> None:
    @env.pv.policy.rule(GlobalThing, READ)
    def global_read(ctx: Context[int, int]) -> list:
        return [true()] if ctx.has_role("author") else []

    async with env.bound(author_ctx()) as session:
        resource = await session.get(GlobalThing, 1)
        assert resource is not None
        assert await env.pv.authorize(session, READ, resource)
        assert await env.pv.authorized_ids(session, READ, GlobalThing, [1, 999]) == [1]
        assert env.pv.validate_create(session, GlobalThing(label="new"))
    async with env.bound(admin_ctx()) as session:
        assert not await env.pv.authorize(session, READ, resource)
        assert await env.pv.authorized_ids(session, READ, GlobalThing, [1]) == []
    async with env.unbound() as session:
        stmt = authorized_select(env.pv.policy, author_ctx(), GlobalThing, "org_id")
        assert [row.id for row in await session.scalars(stmt)] == [1]


async def test_subclass_helpers_use_base_rules_like_automatic_reads(env: Env) -> None:
    @env.pv.policy.rule(Animal, READ)
    def animal_read(ctx: Context[int, int]) -> list:
        return []

    @env.pv.policy.rule(Dog, READ)
    def dog_read(ctx: Context[int, int]) -> list:
        return [true()]  # the base mapper governs supported inheritance

    @env.pv.policy.create_rule(Animal)
    def animal_create(ctx: Context[int, int], resource: Animal) -> bool:
        return False

    async with env.unbound() as session:
        dog = await session.get(Dog, 1)
        assert dog is not None
    async with env.bound(author_ctx()) as session:
        assert list(await session.scalars(select(Dog))) == []
        assert not await env.pv.authorize(session, READ, dog)
        assert await env.pv.authorized_ids(session, READ, Dog, [1, 2]) == []
        assert env.pv.explain(session, READ, Dog).is_default_deny
        assert not env.pv.validate_create(session, Dog(org_id=1, name="new", breed="lab"))
    async with env.unbound() as session:
        stmt = authorized_select(env.pv.policy, author_ctx(), Dog, "org_id")
        assert list(await session.scalars(stmt)) == []


@pytest.mark.parametrize("batch", [False, True])
async def test_checks_keep_reads_inside_flush_hooks_scoped(env: Env, batch: bool) -> None:
    seen = []
    async with env.bound(author_ctx()) as session:
        target = await session.get(Post, env.ids["post1"])
        assert target is not None

        def before_flush(sync_session, flush_context, instances):
            seen.extend(row.id for row in sync_session.scalars(select(Post)))

        event.listen(session.sync_session, "before_flush", before_flush)
        session.add(Post(id=200, author_id=env.ids["alice"], title="pending"))
        if batch:
            await env.pv.authorized_ids(session, READ, Post, [target.id])
        else:
            await env.pv.authorize(session, READ, target)
    assert seen == [env.ids["post1"]]


async def test_subclass_batch_check_excludes_other_base_instances(env: Env) -> None:
    async with env.unbound() as session:
        session.add(Animal(id=200, org_id=1, type="animal", name="other animal"))
        await session.commit()
    async with env.bound(author_ctx()) as session:
        assert [dog.id for dog in await session.scalars(select(Dog))] == [1]
        assert await env.pv.authorized_ids(session, READ, Dog, [1, 200]) == [1]
