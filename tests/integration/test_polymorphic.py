"""Joined-table inheritance is scoped via the base mapper: querying either the
base or a subclass is tenant-filtered."""

from __future__ import annotations

from conftest import Env
from models import Animal, Dog, plain_ctx
from sqlalchemy import select


async def test_select_subclass_is_tenant_filtered(env: Env) -> None:
    async with env.bound(plain_ctx(tenant=1)) as s:
        dogs = (await s.scalars(select(Dog))).all()
        assert {d.id for d in dogs} == {1}
        assert all(d.org_id == 1 for d in dogs)


async def test_select_base_is_tenant_filtered(env: Env) -> None:
    async with env.bound(plain_ctx(tenant=2)) as s:
        animals = (await s.scalars(select(Animal))).all()
        assert all(a.org_id == 2 for a in animals)
        assert {a.id for a in animals} == {2}
