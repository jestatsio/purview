"""Integration fixtures: a fresh in-memory database, the standard policy
installed, and seeded cross-tenant data so leaks are detectable.

Seed (tenant 1 = org 1, tenant 2 = org 2):
  users    alice(1, org1), bob(2, org1), carol(3, org2)
  posts    post1(org1, alice), post1b(org1, bob), post2(org2, carol)
  comments c1a, c1b (org1 on post1), PLANTED(org2 on post1), c2a(org2 on post2)
  animals  dog1(org1), dog2(org2)
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from models import (
    Animal,  # noqa: F401  (registered on Base; needed for create_all + discovery)
    Base,
    Comment,
    Dog,
    GlobalThing,
    Org,
    Post,
    User,
    build_policy,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from purview import Context
from purview.sqlalchemy import Purview, install


@dataclass
class Env:
    sessionmaker: async_sessionmaker[AsyncSession]
    pv: Purview
    ids: dict[str, int]

    @asynccontextmanager
    async def bound(self, ctx: Context[Any, Any]) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as session:
            self.pv.bind(session, ctx)
            yield session

    @asynccontextmanager
    async def unbound(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as session:
            yield session


async def _seed(sm: async_sessionmaker[AsyncSession]) -> dict[str, int]:
    async with sm() as s:  # unbound → guards stand down; org_ids set explicitly
        s.add_all(
            [
                Org(id=1, name="Acme"),
                Org(id=2, name="Globex"),
                User(id=1, org_id=1, name="alice"),
                User(id=2, org_id=1, name="bob"),
                User(id=3, org_id=2, name="carol"),
                Post(id=1, org_id=1, author_id=1, title="p1"),
                Post(id=2, org_id=1, author_id=2, title="p1b"),
                Post(id=3, org_id=2, author_id=3, title="p2"),
                Comment(id=1, org_id=1, post_id=1, body="c1a"),
                Comment(id=2, org_id=1, post_id=1, body="c1b"),
                Comment(id=99, org_id=2, post_id=1, body="PLANTED"),
                Comment(id=3, org_id=2, post_id=3, body="c2a"),
                Dog(id=1, org_id=1, type="dog", name="Rex", breed="lab"),
                Dog(id=2, org_id=2, type="dog", name="Fido", breed="pug"),
                GlobalThing(id=1, label="reference"),
            ]
        )
        await s.commit()
    return {"post1": 1, "post1b": 2, "post2": 3, "alice": 1, "bob": 2, "planted": 99}


def _backends() -> list[tuple[str, str]]:
    """sqlite always; Postgres too when PURVIEW_TEST_POSTGRES_URL is set (CI)."""
    backends = [("sqlite", "sqlite+aiosqlite:///:memory:")]
    pg = os.environ.get("PURVIEW_TEST_POSTGRES_URL")
    if pg:
        backends.append(("postgres", pg))
    return backends


@pytest.fixture(params=_backends(), ids=[name for name, _ in _backends()])
async def env(request: pytest.FixtureRequest) -> AsyncIterator[Env]:
    backend, url = request.param
    if backend == "sqlite":
        engine = create_async_engine(
            url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    else:
        engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, build_policy(), tenant_column="org_id")
    ids = await _seed(sm)
    try:
        yield Env(sm, pv, ids)
    finally:
        pv.uninstall()
        await engine.dispose()
