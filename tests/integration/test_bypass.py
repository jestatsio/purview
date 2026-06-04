"""The escape hatch disables enforcement within the block and — critically —
re-enables it on exit. A bypass that leaked state afterwards would be a footgun."""

from __future__ import annotations

import pytest
from conftest import Env
from models import Post, plain_ctx
from sqlalchemy import select

from purview.sqlalchemy import bypass


async def test_bypass_disables_then_reenables_filtering(env: Env) -> None:
    async with env.bound(plain_ctx(tenant=1)) as s:
        assert (await s.scalars(select(Post))).all() == []  # denied before

        with bypass(reason="integration test admin task"):
            everything = (await s.scalars(select(Post))).all()
            assert {p.id for p in everything} == {1, 2, 3}  # all rows, all tenants

        assert (await s.scalars(select(Post))).all() == []  # denied again after


def test_bypass_requires_a_reason() -> None:
    with pytest.raises(ValueError, match="reason"), bypass(reason="   "):
        pass
