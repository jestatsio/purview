"""Demo data. Run ``python -m tracker.seed`` after ``alembic upgrade head``.

Seeding uses an *unbound* session (no Context), so the guards stand down and the
ids are inserted exactly as given — the normal way to load fixtures or run an import.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from .db import SessionLocal, engine
from .models import LegacyImport, Membership, Project, Task, User, Workspace

# Deterministic ids so the demo (and the smoke test) can assert on them.
WS1, WS2 = uuid.UUID(int=1), uuid.UUID(int=2)
ALICE, BOB, CAROL, DAVE = (uuid.UUID(int=n) for n in (11, 12, 13, 14))
TASK_ALICE, TASK_BOB, TASK_CAROL = (uuid.UUID(int=n) for n in (101, 102, 103))


async def seed_demo(sessionmaker: async_sessionmaker) -> None:
    async with sessionmaker() as session:
        # The models use ForeignKey columns without relationships, so insert the
        # parents (and flush) before the rows that reference them. Integer ids are
        # left to autoincrement so the app's later inserts don't collide.
        p1 = Project(workspace_id=WS1, owner_id=ALICE, name="ws1-project")
        p2 = Project(workspace_id=WS2, owner_id=CAROL, name="ws2-project")
        session.add_all(
            [
                Workspace(id=WS1, name="Acme"),
                Workspace(id=WS2, name="Globex"),
                User(id=ALICE, name="alice"),
                User(id=BOB, name="bob"),
                User(id=CAROL, name="carol"),
                User(id=DAVE, name="dave"),
                p1,
                p2,
                LegacyImport(account_id=WS1, payload="ws1-legacy"),
                LegacyImport(account_id=WS2, payload="ws2-legacy"),
            ]
        )
        await session.flush()  # populates p1.id / p2.id
        session.add_all(
            [
                Membership(workspace_id=WS1, user_id=ALICE, role="member"),
                Membership(workspace_id=WS1, user_id=BOB, role="member"),
                Membership(workspace_id=WS1, user_id=DAVE, role="admin"),
                Membership(workspace_id=WS2, user_id=CAROL, role="admin"),
                Task(id=TASK_ALICE, workspace_id=WS1, project_id=p1.id, assignee_id=ALICE, title="alice-task"),
                Task(id=TASK_BOB, workspace_id=WS1, project_id=p1.id, assignee_id=BOB, title="bob-task"),
                Task(id=TASK_CAROL, workspace_id=WS2, project_id=p2.id, assignee_id=CAROL, title="carol-task"),
            ]
        )
        await session.commit()


async def _main() -> None:
    await seed_demo(SessionLocal)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
