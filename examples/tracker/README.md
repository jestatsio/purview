# Purview Tracker

A small multi-tenant project tracker — **FastAPI + SQLAlchemy 2.0 async + Alembic +
Postgres**, wired with [Purview](https://github.com/jestatsio/purview). The same
policy filters task lists, checks updates, and validates project creation.

| Capability | Where |
|---|---|
| Multi-tenancy (the session boundary) | scoped by `workspace_id` |
| **Per-model tenant column** | `LegacyImport` is scoped by `account_id` |
| **Composite primary key** | `Membership(workspace_id, user_id)` |
| **UUID primary keys** | `Workspace`, `User`, `Task` |
| **Read rule** | members see their own tasks; admins see all in the workspace |
| **Create rule** | a project's `owner_id` must be its creator |

## Run

Start with Python 3.11+, [uv](https://docs.astral.sh/uv/), and a local PostgreSQL
server. Install the current checkout and its example tools from the repository root:

```bash
git clone https://github.com/jestatsio/purview.git
cd purview
uv sync --all-extras --locked
source .venv/bin/activate
cd examples/tracker

createdb tracker
export DATABASE_URL=postgresql+asyncpg://localhost/tracker

alembic upgrade head
python -m tracker.seed
uvicorn tracker.app:app --reload
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` and set
`$env:DATABASE_URL` in PowerShell. Adjust the database URL for your local PostgreSQL
user and password. Seed a newly created database once.

Open <http://127.0.0.1:8000/docs> to explore the API. The `X-Workspace-Id` and
`X-User-Id` headers are a demo identity mechanism. Production applications should
derive these values from an authenticated session or verified token.

Alice is a *member* of workspace 1, so she only sees her own tasks:

```bash
curl -s http://127.0.0.1:8000/tasks \
  -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001" \
  -H "X-User-Id: 00000000-0000-0000-0000-00000000000b"
```

The response contains `alice-task`. Change the user ID to
`00000000-0000-0000-0000-00000000000e` for Dave, an admin who also sees `bob-task`.
The route and query are identical. The policy determines which rows are visible.

Create and update payloads use Pydantic models. Missing fields, invalid UUIDs,
empty names or titles, and values longer than their database columns return HTTP
422 before a write occurs.

## Test

From the repository root:

```bash
uv run --locked --all-extras pytest examples/tracker/test_smoke.py
```

The HTTP tests seed two workspaces in a temporary SQLite database. They cover tenant
isolation, read/create rules, composite keys, per-model tenant columns, cross-tenant
404s, and request validation. They do not connect to the demo's `DATABASE_URL`.

To run the same tests against PostgreSQL as well, use a test database whose user can
create schemas:

```bash
createdb purview_test
export PURVIEW_TEST_POSTGRES_URL=postgresql+asyncpg://localhost/purview_test
uv run --locked --all-extras pytest examples/tracker/test_smoke.py
```

Each PostgreSQL test creates and removes a uniquely named schema. No pre-existing
tables are dropped, and no migration or manual seed step is needed for the tests.

## How it's wired

- [`tracker/models.py`](tracker/models.py) — the schema.
- [`tracker/policy.py`](tracker/policy.py) — the policy (read rule, create rule,
  per-model column, globals).
- [`tracker/app.py`](tracker/app.py) — `install(...)`, the context dependency, and the
  routes.
- [`migrations/`](migrations/) — the Alembic migration.
