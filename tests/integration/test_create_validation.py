"""Create validation checks the proposed tenant before a row exists; the write
guard is the structural backstop at flush time."""

from __future__ import annotations

from conftest import Env
from models import Post, author_ctx


async def test_accepts_unset_tenant(env: Env) -> None:
    async with env.bound(author_ctx(tenant=1)) as s:
        assert env.pv.validate_create(s, Post(id=300, author_id=1, title="x")) is True


async def test_accepts_matching_tenant(env: Env) -> None:
    async with env.bound(author_ctx(tenant=1)) as s:
        assert env.pv.validate_create(s, Post(id=301, org_id=1, author_id=1, title="x")) is True


async def test_rejects_foreign_tenant(env: Env) -> None:
    async with env.bound(author_ctx(tenant=1)) as s:
        assert env.pv.validate_create(s, Post(id=302, org_id=2, author_id=1, title="x")) is False
