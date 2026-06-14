"""explain() reports the same predicate the read guard applies — proven by
comparing the explanation against the rows an actual filtered query returns."""

from __future__ import annotations

from conftest import Env
from models import Comment, Org, Post, admin_ctx, author_ctx, plain_ctx
from sqlalchemy import select

from purview import READ, Context


async def test_explain_matches_authors_filtered_read(env: Env) -> None:
    ctx = author_ctx(user_id=env.ids["alice"])
    async with env.bound(ctx) as session:
        exp = env.pv.explain(session, READ, Post)
        rows = {p.id for p in (await session.scalars(select(Post))).all()}

    assert exp.is_default_deny is False
    assert f"author_id = {env.ids['alice']}" in exp.row_sql
    assert exp.tenant_scoped is True
    assert rows == {env.ids["post1"]}  # only alice's post


async def test_explain_default_deny_for_plain_actor(env: Env) -> None:
    async with env.bound(plain_ctx()) as session:
        exp = env.pv.explain(session, READ, Post)
        rows = (await session.scalars(select(Post))).all()

    assert exp.is_default_deny is True
    assert exp.row_sql == "false"
    assert rows == []  # the explanation predicted the empty read


async def test_explain_unruled_model_is_tenant_wide(env: Env) -> None:
    async with env.bound(plain_ctx()) as session:
        exp = env.pv.explain(session, READ, Comment)
    assert exp.is_default_deny is False
    assert exp.row_sql == "true"
    assert exp.tenant_scoped is True


async def test_explain_global_model_has_no_tenant_scope(env: Env) -> None:
    async with env.bound(admin_ctx()) as session:
        exp = env.pv.explain(session, READ, Org)
    assert exp.tenant_scoped is False
    assert exp.tenant_sql is None


async def test_explain_accepts_a_bare_context_without_a_session(env: Env) -> None:
    exp = env.pv.explain(author_ctx(user_id=2), READ, Post)
    assert "author_id = 2" in exp.row_sql


async def test_explain_renders_human_readable(env: Env) -> None:
    exp = env.pv.explain(author_ctx(), READ, Post)
    text = str(exp)
    assert "Post" in text and "active roles" in text and "author" in text


async def test_explain_update_reports_its_own_stricter_rule(env: Env) -> None:
    # The standard policy registers a stricter update rule than read.
    exp = env.pv.explain(author_ctx(user_id=1), "update", Post)
    assert exp.governing_action == "update"


async def test_explain_expands_role_hierarchy(env: Env) -> None:
    # An org_admin reads the whole tenant via its own rule; confirm explain reflects
    # the active roles it was given.
    ctx = Context(999, 1, frozenset({"org_admin"}))
    exp = env.pv.explain(ctx, READ, Post)
    assert "org_admin" in exp.active_roles
