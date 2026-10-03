"""HTTP smoke tests using isolated databases, never the demo's DATABASE_URL.

SQLite runs by default. Set PURVIEW_TEST_POSTGRES_URL to also exercise PostgreSQL
in a unique schema that is removed after each test.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from tracker import app as tracker_app
from tracker.models import Base
from tracker.seed import ALICE, BOB, CAROL, DAVE, TASK_BOB, TASK_CAROL, WS1, WS2, seed_demo


@pytest.fixture(params=["sqlite", "postgres"])
async def test_engine(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    schema = None
    if request.param == "postgres":
        url = os.environ.get("PURVIEW_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Set PURVIEW_TEST_POSTGRES_URL to test PostgreSQL")
        engine = create_async_engine(url, poolclass=NullPool)
        schema = f"purview_tracker_{uuid.uuid4().hex}"
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = engine.execution_options(schema_translate_map={None: schema})
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tracker.db'}")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        try:
            if schema is not None:
                async with engine.begin() as connection:
                    await connection.execute(DropSchema(schema, cascade=True))
        finally:
            await engine.dispose()


@pytest.fixture
async def client(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    sessionmaker = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(tracker_app, "SessionLocal", sessionmaker)
    await seed_demo(sessionmaker)
    transport = ASGITransport(app=tracker_app.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


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


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "project"},
        {"name": "project", "owner_id": "invalid-uuid"},
        {"name": "", "owner_id": str(ALICE)},
        {"name": "x" * 101, "owner_id": str(ALICE)},
        {"name": None, "owner_id": str(ALICE)},
    ],
)
async def test_invalid_project_payload_returns_422(
    client: AsyncClient, payload: dict[str, object]
) -> None:
    response = await client.post("/projects", headers=_as(WS1, ALICE), json=payload)
    assert response.status_code == 422
    projects = await client.get("/projects", headers=_as(WS1, ALICE))
    assert [project["name"] for project in projects.json()] == ["ws1-project"]


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": None}, {"title": "x" * 201}])
async def test_invalid_task_payload_returns_422(
    client: AsyncClient, payload: dict[str, object]
) -> None:
    response = await client.patch(f"/tasks/{TASK_BOB}", headers=_as(WS1, BOB), json=payload)
    assert response.status_code == 422
    task = await client.get(f"/tasks/{TASK_BOB}", headers=_as(WS1, BOB))
    assert task.json()["title"] == "bob-task"
