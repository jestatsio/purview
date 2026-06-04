# Purview Tracker — dogfood example

A small multi-tenant project tracker — **FastAPI + SQLAlchemy 2.0 async + Alembic +
Postgres**, wired with [Purview](https://github.com/jestatsio/purview). It's the
real-app proof that Purview works on a realistic schema: every 0.2 capability is
exercised here, not just in unit tests.

| Capability | Where |
|---|---|
| Multi-tenancy (the session boundary) | scoped by `workspace_id` |
| **Per-model tenant column** | `LegacyImport` is scoped by `account_id` |
| **Composite primary key** | `Membership(workspace_id, user_id)` |
| **UUID primary keys** | `Workspace`, `User`, `Task` |
| **Read rule** | members see their own tasks; admins see all in the workspace |
| **Create rule** | a project's `owner_id` must be its creator |

## Run

```bash
cd examples/tracker
pip install -r requirements.txt

createdb tracker
export DATABASE_URL=postgresql+asyncpg://localhost/tracker

alembic upgrade head            # create the schema (real migration)
python -m tracker.seed          # demo data
uvicorn tracker.app:app --reload
```

Identify yourself with the `X-Workspace-Id` / `X-User-Id` headers (a stand-in for
your real auth). For example, alice is a *member* of workspace 1, so she only sees
her own tasks:

```bash
curl -s localhost:8000/tasks \
  -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001" \
  -H "X-User-Id:      00000000-0000-0000-0000-00000000000b"   # alice
```

while dave (an *admin* of workspace 1) sees every task in the workspace — same route,
same query, different rows, all from one policy definition.

## Test

With `DATABASE_URL` set and the schema migrated:

```bash
pytest test_smoke.py
```

The smoke test seeds two workspaces and asserts — over real HTTP — tenant isolation,
the read/create rules, the composite-PK and per-model-column models, and cross-tenant
404s.

## How it's wired

- [`tracker/models.py`](tracker/models.py) — the schema.
- [`tracker/policy.py`](tracker/policy.py) — the policy (read rule, create rule,
  per-model column, globals).
- [`tracker/app.py`](tracker/app.py) — `install(...)`, the context dependency, and the
  routes.
- [`migrations/`](migrations/) — the Alembic migration.
