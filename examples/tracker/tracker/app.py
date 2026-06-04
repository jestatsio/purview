"""The tracker FastAPI app, wired with Purview.

Auth here is a stand-in: the ``X-Workspace-Id`` / ``X-User-Id`` headers identify the
actor, and roles are loaded from ``Membership``. In a real app this is your JWT /
session middleware — Purview consumes whatever authenticated identity you produce.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from purview import Context, PurviewForbidden
from purview.fastapi import authorize_or_403, context_binder, install_error_handlers
from purview.sqlalchemy import install

from .db import SessionLocal
from .models import Base, LegacyImport, Membership, Project, Task
from .policy import build_policy

pv = install(Base, build_policy(), tenant_column="workspace_id")

app = FastAPI(title="Purview Tracker (dogfood)")
install_error_handlers(app)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_context(
    x_workspace_id: uuid.UUID = Header(),
    x_user_id: uuid.UUID = Header(),
) -> Context[uuid.UUID, uuid.UUID]:
    async with SessionLocal() as session:  # auth bootstrap: unbound role lookup
        roles = set(
            await session.scalars(
                select(Membership.role).where(
                    Membership.workspace_id == x_workspace_id,
                    Membership.user_id == x_user_id,
                )
            )
        )
    if not roles:
        raise HTTPException(status_code=401, detail="not a member of this workspace")
    return Context(user_id=x_user_id, tenant_id=x_workspace_id, roles=frozenset(roles))


bound = context_binder(pv, get_session, get_context)


@app.get("/projects")
async def list_projects(session: AsyncSession = Depends(bound)) -> list[dict[str, Any]]:
    return [{"id": p.id, "name": p.name} for p in await session.scalars(select(Project))]


@app.post("/projects", status_code=201)
async def create_project(
    payload: dict[str, Any], session: AsyncSession = Depends(bound)
) -> dict[str, Any]:
    ctx = pv.context(session)
    project = Project(
        workspace_id=ctx.tenant_id,
        owner_id=uuid.UUID(payload["owner_id"]),
        name=payload["name"],
    )
    if not pv.validate_create(session, project):  # create rule: owner must be the creator
        raise PurviewForbidden("you may only create projects you own")
    session.add(project)
    await session.commit()
    return {"id": project.id, "name": project.name}


@app.get("/tasks")
async def list_tasks(session: AsyncSession = Depends(bound)) -> list[dict[str, Any]]:
    # role-shaped: members see their assigned tasks, admins see all in the workspace
    return [{"id": str(t.id), "title": t.title} for t in await session.scalars(select(Task))]


@app.get("/tasks/{task_id}")
async def get_task(task_id: uuid.UUID, session: AsyncSession = Depends(bound)) -> dict[str, Any]:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="not found")
    return {"id": str(task.id), "title": task.title}


@app.patch("/tasks/{task_id}")
async def update_task(
    task_id: uuid.UUID, payload: dict[str, Any], session: AsyncSession = Depends(bound)
) -> dict[str, Any]:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="not found")
    await authorize_or_403(pv, session, "update", task)
    task.title = payload["title"]
    await session.commit()
    return {"id": str(task.id), "title": task.title}


@app.get("/members")
async def list_members(session: AsyncSession = Depends(bound)) -> list[dict[str, Any]]:
    # composite-PK model, tenant-scoped by workspace_id
    rows = await session.scalars(select(Membership))
    return [{"user_id": str(m.user_id), "role": m.role} for m in rows]


@app.get("/legacy")
async def list_legacy(session: AsyncSession = Depends(bound)) -> list[dict[str, Any]]:
    # scoped by its own account_id column, not workspace_id
    return [{"id": r.id, "payload": r.payload} for r in await session.scalars(select(LegacyImport))]
