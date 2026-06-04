"""End-to-end smoke test for the tracker dogfood, over real HTTP against the
database in DATABASE_URL (run `alembic upgrade head` first). Validates tenant
isolation, the read/create rules, and the composite-PK + per-model-column models.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from tracker.app import app
from tracker.db import SessionLocal, engine
from tracker.models import Base
from tracker.seed import ALICE, BOB, CAROL, DAVE, TASK_BOB, TASK_CAROL, WS1, WS2, seed_demo


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await seed_demo(SessionLocal)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await engine.dispose()


def _as(workspace: uuid.UUID, user: uuid.UUID) -> dict[str, str]:
    return {"X-Workspace-Id": str(workspace), "X-User-Id": str(user)}


async def test_member_sees_only_their_tasks(client: AsyncClient) -> None:
    resp = await client.get("/tasks", headers=_as(WS1, ALICE))
    assert {t["title"] for t in resp.json()} == {"alice-task"}


async def test_admin_sees_all_tasks_in_workspace(client: AsyncClient) -> None:
    resp = await client.get("/tasks", headers=_as(WS1, DAVE))
    assert {t["title"] for t in resp.json()} == {"alice-task", "bob-task"}


async def test_other_workspace_is_isolated(client: AsyncClient) -> None:
    assert {t["title"] for t in (await client.get("/tasks", headers=_as(WS2, CAROL))).json()} == {
        "carol-task"
    }
    assert (await client.get(f"/tasks/{TASK_CAROL}", headers=_as(WS1, DAVE))).status_code == 404


async def test_member_updates_own_task_but_not_anothers(client: AsyncClient) -> None:
    ok = await client.patch(f"/tasks/{TASK_BOB}", headers=_as(WS1, BOB), json={"title": "edited"})
    assert ok.status_code == 200
    # alice can't even see bob's task, so the update 404s rather than leaking it
    nope = await client.patch(f"/tasks/{TASK_BOB}", headers=_as(WS1, ALICE), json={"title": "x"})
    assert nope.status_code == 404


async def test_create_rule_requires_owner_is_creator(client: AsyncClient) -> None:
    mine = await client.post(
        "/projects", headers=_as(WS1, ALICE), json={"name": "mine", "owner_id": str(ALICE)}
    )
    assert mine.status_code == 201
    forged = await client.post(
        "/projects", headers=_as(WS1, ALICE), json={"name": "theirs", "owner_id": str(BOB)}
    )
    assert forged.status_code == 403


async def test_composite_pk_members_are_scoped(client: AsyncClient) -> None:
    members = (await client.get("/members", headers=_as(WS1, DAVE))).json()
    assert {m["role"] for m in members} == {"member", "admin"}
    assert len(members) == 3  # ws1 only; carol (ws2) excluded


async def test_per_model_column_legacy_is_scoped(client: AsyncClient) -> None:
    # LegacyImport is scoped by account_id, not workspace_id
    ws1 = (await client.get("/legacy", headers=_as(WS1, ALICE))).json()
    assert {r["payload"] for r in ws1} == {"ws1-legacy"}


async def test_non_member_is_rejected(client: AsyncClient) -> None:
    assert (await client.get("/tasks", headers=_as(WS2, ALICE))).status_code == 401
