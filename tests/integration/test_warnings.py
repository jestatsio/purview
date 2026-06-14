"""Opt-in footgun warnings: a query on an unbound session and a raw/non-ORM
statement on a bound one warn when warn_on_unfiltered=True, and never otherwise."""

from __future__ import annotations

import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from conftest import Env
from models import Base, Org, Post, User, author_ctx, build_policy
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from purview import PurviewWarning
from purview.sqlalchemy import Purview, install


@asynccontextmanager
async def _env(*, warn: bool) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], Purview]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, build_policy(), tenant_column="org_id", warn_on_unfiltered=warn)
    async with sm() as s:
        s.add_all(
            [
                Org(id=1, name="Acme"),
                User(id=1, org_id=1, name="alice"),
                Post(id=1, org_id=1, author_id=1, title="p"),
            ]
        )
        await s.commit()
    try:
        yield sm, pv
    finally:
        pv.uninstall()
        await engine.dispose()


async def test_raw_text_on_bound_session_warns() -> None:
    async with _env(warn=True) as (sm, pv), sm() as s:
        pv.bind(s, author_ctx())
        with pytest.warns(PurviewWarning, match="raw/non-ORM"):
            await s.execute(text("SELECT * FROM post"))


async def test_query_on_unbound_session_warns() -> None:
    async with _env(warn=True) as (sm, _pv), sm() as s:
        with pytest.warns(PurviewWarning, match="no bound Purview context"):
            await s.scalars(select(Post))


async def test_orm_select_on_bound_session_never_warns() -> None:
    async with _env(warn=True) as (sm, pv), sm() as s:
        pv.bind(s, author_ctx())
        with warnings.catch_warnings():
            warnings.simplefilter("error", PurviewWarning)
            await s.scalars(select(Post))  # filtered ORM read → no warning


async def test_default_install_is_silent(env: Env) -> None:
    # The shared env installs without warn_on_unfiltered; nothing should warn.
    with warnings.catch_warnings():
        warnings.simplefilter("error", PurviewWarning)
        async with env.bound(author_ctx()) as s:
            await s.execute(text("SELECT * FROM post"))
        async with env.unbound() as s:
            await s.scalars(select(Post))
