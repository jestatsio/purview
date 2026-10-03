# Purview

**Authorization that speaks SQLAlchemy.**

[![CI](https://github.com/jestatsio/purview/actions/workflows/ci.yml/badge.svg)](https://github.com/jestatsio/purview/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/purview-authz)](https://pypi.org/project/purview-authz/)
[![Python](https://img.shields.io/pypi/pyversions/purview-authz)](https://pypi.org/project/purview-authz/)
[![Documentation](https://img.shields.io/badge/docs-online-087e8b)](https://jestatsio.github.io/purview/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Row-level authorization and tenant isolation for SQLAlchemy 2.0, with a lightweight
FastAPI adapter. Write policies as Python functions returning SQLAlchemy predicates.
Purview uses those predicates to filter ORM reads and answer explicit permission
checks in the database. No policy server or separate language required.

**[Documentation](https://jestatsio.github.io/purview/)** ·
[Quickstart](https://jestatsio.github.io/purview/quickstart/) ·
[API reference](https://jestatsio.github.io/purview/reference/) ·
[Security boundary](https://jestatsio.github.io/purview/THREAT_MODEL/)

## Install

Requires **Python 3.11+** and **SQLAlchemy 2.0**. The distribution is
`purview-authz`, and the Python import is `purview`.

```bash
# A new or existing uv project
uv add "purview-authz[sqlite]"

# Or use pip in a virtual environment
python -m pip install "purview-authz[sqlite]"
```

Choose extras for your application:

| Install | Includes |
| --- | --- |
| `purview-authz` | Purview and SQLAlchemy's asyncio support |
| `purview-authz[sqlite]` | Also includes the `aiosqlite` driver |
| `purview-authz[postgres]` | Also includes the `asyncpg` driver |
| `purview-authz[fastapi,postgres]` | FastAPI adapter and PostgreSQL driver |

## One policy, filtered reads

```python
from sqlalchemy import select
from purview import READ, Context, Policy
from purview.sqlalchemy import install

policy = Policy()


@policy.rule(Post, READ)
def read_posts(ctx: Context):
    return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []


pv = install(Base, policy, strict=True)

async with sessions() as session:
    pv.bind(session, Context(user_id=42, tenant_id=1, roles={"author"}))
    posts = (await session.scalars(select(Post))).all()
```

Here, `Base`, `Post`, and `sessions` are your application's SQLAlchemy models and
async session factory. The tenant predicate and read policy apply together, so this
query returns only posts by author 42 in tenant 1.

**[Run the complete SQLite quickstart](https://jestatsio.github.io/purview/quickstart/)**
or inspect [the runnable script](examples/quickstart.py). It creates its own models,
database, and sample data.

A registered rule returning `[]` denies access. The example enables `strict=True`,
which also denies access to scoped models with no read rule. Without strict mode,
those models are readable throughout the bound tenant.

## What Purview handles

- **ORM read filtering:** selects, database loads through `session.get()`, and
  supported eager or awaitable relationship loads on a bound session.
- **Tenant checks on object writes:** stamp tenant IDs on new objects and reject
  cross-tenant attachments and tenant changes during normal ORM flushes.
- **Explicit authorization:** `await pv.authorize(...)`, batch
  `await pv.authorized_ids(...)`, and `pv.validate_create(...)`.
- **Policy tools:** role hierarchies, per-model tenant fields, predicate explanations,
  and audits for models left readable tenant-wide.

Use a **fresh session per actor/request**, and bind it before loading application
data. Your app authenticates the actor and resolves trusted tenant membership and
roles. Call authorization helpers before modifying or deleting an object, and call
`validate_create()` before adding it when you use create rules.

Raw SQL, Core statements, bulk DML, unbound sessions, and explicit bypass blocks
are outside automatic enforcement. Global models are exempt from automatic
filtering. Purview is an application-layer control, not database row-level security.
Read the [security boundary](https://jestatsio.github.io/purview/THREAT_MODEL/) before
integrating it into request handlers.

## Build with Purview

| Guide | Start here for |
| --- | --- |
| [Installation](https://jestatsio.github.io/purview/installation/) | Drivers, extras, and a clean environment |
| [Quickstart](https://jestatsio.github.io/purview/quickstart/) | A runnable SQLite example and how it works |
| [Writing policies](https://jestatsio.github.io/purview/policies/) | Grants, defaults, create rules, and tenant configuration |
| [FastAPI integration](https://jestatsio.github.io/purview/fastapi/) | Request dependencies, explicit checks, and HTTP errors |
| [Debugging policies](https://jestatsio.github.io/purview/debugging/) | Explain SQL and audit visibility |
| [Migrating from Oso](https://jestatsio.github.io/purview/MIGRATING_FROM_OSO/) | Map existing policy concepts to Purview |
| [Tracker example](examples/tracker/) | FastAPI, Alembic, and PostgreSQL together |

## Contribute

```bash
git clone https://github.com/jestatsio/purview.git
cd purview
uv sync --locked --all-extras
uv run --locked --all-extras pytest
uv run --locked --all-extras mypy
uv run --locked --all-extras ruff check .
uv run --locked --all-extras mkdocs serve
```

See [Contributing](CONTRIBUTING.md) for the development workflow and PostgreSQL
tests, [Releasing](RELEASING.md) for the release process, and
[Security](SECURITY.md) for private vulnerability reporting.

MIT licensed. See [LICENSE](LICENSE).
