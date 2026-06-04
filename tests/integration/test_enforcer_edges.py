"""Edge behaviours of the enforcer facade and the explicit filter helper."""

from __future__ import annotations

import pytest
from conftest import Env
from models import Post, author_ctx
from sqlalchemy import select

from purview import Policy
from purview.sqlalchemy import authorized_select, install


async def test_authorized_select_filters_off_an_unbound_session(env: Env) -> None:
    # No guard fires on an unbound session, so the explicit predicate is the
    # sole authority — proving authorized_select stands alone.
    stmt = authorized_select(
        env.pv.policy,
        author_ctx(user_id=env.ids["alice"], tenant=1),
        Post,
        env.pv.tenant_column,
    )
    async with env.unbound() as s:
        rows = (await s.scalars(stmt)).all()
        assert {p.id for p in rows} == {env.ids["post1"]}


async def test_unbound_session_is_unfiltered(env: Env) -> None:
    async with env.unbound() as s:
        rows = (await s.scalars(select(Post))).all()
        assert {p.id for p in rows} == {1, 2, 3}  # every tenant — guard stood down


def test_install_is_idempotent(env: Env) -> None:
    assert env.pv.install() is env.pv  # second install is a no-op


def test_uninstall_is_safe_to_repeat(env: Env) -> None:
    env.pv.uninstall()
    env.pv.uninstall()  # no-op the second time


def test_install_rejects_a_non_declarative_target() -> None:
    with pytest.raises(TypeError):
        install(object(), Policy(), tenant_column="org_id")
