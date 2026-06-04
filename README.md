# Purview

[![CI](https://github.com/jestatsio/purview/actions/workflows/ci.yml/badge.svg)](https://github.com/jestatsio/purview/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/purview-authz)](https://pypi.org/project/purview-authz/)
[![Python](https://img.shields.io/pypi/pyversions/purview-authz)](https://pypi.org/project/purview-authz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Row-level authorization and multi-tenancy for FastAPI + SQLAlchemy.** Define a
policy once as SQLAlchemy column expressions and get both yes/no checks and query
filtering from the same rule — so the check and the filter can never disagree.

> Drift between "can this actor do this?" and "which rows can they see?" is a data
> leak. Purview makes both come from one definition, so they cannot drift.

```python
@policy.rule(Post, "read")
def read_post(ctx: Context) -> list[ColumnElement[bool]]:
    rules = []
    if ctx.has_role("author"):
        rules.append(Post.author_id == ctx.user_id)   # authors see their own
    if ctx.has_role("org_admin"):
        rules.append(true())                           # admins see the whole tenant
    return rules                                       # OR-combined; empty = deny
```

That one rule now powers a filtered `select(Post)` **and** an
`authorize(session, "read", post)` check.

## Why this exists

Authentication generalizes; authorization does not, because it is welded to your
domain model and data layer. The hard, valuable part is **data filtering**:
shaping queries so a user only ever loads rows they're allowed to see, pushed into
SQL rather than filtered in Python after the fact. [Oso](https://www.osohq.com/)
solved this well and then deprecated its open-source library, leaving no idiomatic
Python answer. Purview targets that gap for the FastAPI + SQLAlchemy stack
specifically — in-process, async-first, no external policy service.

## Install

```bash
pip install purview-authz            # core + SQLAlchemy
pip install "purview-authz[fastapi]" # plus the FastAPI adapter
```

The distribution is `purview-authz`; the import package is `purview`. Requires
Python 3.11+ and SQLAlchemy 2.0+.

## Quickstart

```python
from sqlalchemy import true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from purview import Context, Policy, READ
from purview.sqlalchemy import install

class Base(DeclarativeBase): ...

class Org(Base):                       # the tenant root — global
    __tablename__ = "org"
    id: Mapped[int] = mapped_column(primary_key=True)

class Post(Base):                      # tenant-scoped (has the tenant column)
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column()
    author_id: Mapped[int] = mapped_column()

policy = Policy()
policy.global_model(Org)               # opt Org out of tenant scoping

@policy.rule(Post, READ)
def read_post(ctx: Context):
    return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []

pv = install(Base, policy, tenant_column="org_id")   # wires the guards; validates models
```

Bind a request's session to its actor, then query normally — reads are filtered
automatically:

```python
async with async_session() as session:
    pv.bind(session, Context(user_id=42, tenant_id=1, roles={"author"}))

    posts = await session.scalars(select(Post))          # only org 1 + authored by 42
    one   = await session.get(Post, 99)                  # None if not visible
    ok    = await pv.authorize(session, "update", post)  # yes/no for one object
    ids   = await pv.authorized_ids(session, "read", Post, [1, 2, 3])  # the allowed subset
```

## Core concepts

**One definition, two forms.** A rule returns boolean `ColumnElement` predicates.
As a `.where(...)` they filter a collection; wrapped in
`EXISTS (SELECT 1 ... AND <predicate>)` they check a single object. The database
evaluates both, so relationship and join predicates work without re-implementing
SQL in Python.

**Roles select predicates.** An actor's tenant-scoped roles decide which
predicates apply for `(action, model)`. Grants are OR-combined; **no granting role
means no rows — default deny.**

**Tenancy is the session boundary.** One session is bound to exactly one tenant.
A `do_orm_execute` hook scopes every read (including lazy and eager relationship
loads) to that tenant; a `before_flush` hook auto-stamps the tenant on inserts and
refuses writes that would cross the boundary.

**Secure by default.** Every mapped model is tenant-scoped automatically. Opt a
model out with `policy.global_model(...)`. `install()` **raises** if a non-global
model lacks the tenant column — an unscoped table fails at startup, never leaks at
runtime.

**`read` drives filtering.** It is the action that shapes collections. Other
actions are instance-level checks; `update`/`delete` reuse the `read` predicate
unless you register a stricter rule for them.

**Within-tenant default.** A scoped model with *no* read rule is visible
tenant-wide (tenant isolation still applies). Pass `install(..., strict=True)` to
flip this to within-tenant **default deny** — every model then needs an explicit
rule to grant any access. The cross-tenant boundary is enforced identically in
both modes.

## The enforcement boundary

Inside the boundary: ORM `select`s, `session.get`, relationship loads, and flushes
on a bound session.

Outside the boundary (documented, not enforced):

- **Raw SQL and Core `text()`** — Purview shapes ORM statements, not hand-written SQL.
- **Implicit lazy loads under async** — these raise `MissingGreenlet` in SQLAlchemy
  regardless; use `selectinload(...)` or `await obj.awaitable_attrs.x`. Eager and
  awaitable lazy loads *are* filtered.
- **Unbound sessions** — a session with no bound context is not filtered (this is
  how you seed and run migrations).

### Escape hatch

One loud, greppable bypass for admin tooling and migrations:

```python
from purview.sqlalchemy import bypass

with bypass(reason="nightly billing rollup"):
    ...   # enforcement stands down on this task; the reason is logged at WARNING
```

## FastAPI

```python
from purview.fastapi import context_binder, authorize_or_403, install_error_handlers

install_error_handlers(app)                              # PurviewForbidden -> 403
bound = context_binder(pv, get_session, get_context)     # binds the actor per request

@app.get("/posts")
async def list_posts(session: AsyncSession = Depends(bound)):
    return (await session.scalars(select(Post))).all()   # auto-filtered

@app.patch("/posts/{post_id}")
async def edit(post_id: int, session: AsyncSession = Depends(bound)):
    post = await session.get(Post, post_id)              # 404 if not visible
    await authorize_or_403(pv, session, "update", post)  # 403 if not permitted
    ...
```

See [`tests/examples/test_blog_app.py`](tests/examples/test_blog_app.py) for a
complete, runnable app.

## How it compares

|                          | Purview | Oso (OSS) | Cerbos | Casbin |
|--------------------------|:-------:|:---------:|:------:|:------:|
| In-process (no network)  | ✅ | ✅ | ❌ service | ✅ |
| SQL data filtering       | ✅ | ✅ | ✅ | ❌ |
| One def → check + filter  | ✅ | ✅ | ➖ | ❌ |
| SQLAlchemy 2.0 async     | ✅ | ❌ | ✅ adapter | ➖ |
| Policy in native Python  | ✅ | Polar DSL | YAML | model+CSV |
| Maintained               | ✅ | deprecated 2023 | ✅ | ✅ |

## Scope (v1)

**In:** row-level filtering, multi-tenancy as a structural concern, yes/no checks
and query filtering from one definition, SQLAlchemy 2.0 async, FastAPI adapter.

**Out (for now):** field-level authorization (belongs in serialization),
non-SQLAlchemy ORMs, a hosted policy service, Postgres RLS as a compile target.

## Development

```bash
uv run --extra dev pytest          # unit + integration + the example app
uv run --extra dev mypy            # strict typing is a project invariant
uv run --extra dev ruff check .
```

Postgres fidelity is exercised in CI; set `PURVIEW_TEST_POSTGRES_URL` to run the
integration matrix against a local Postgres too.

Releases publish to PyPI on a version tag via Trusted Publishing (no stored token);
the version is derived from the tag. See [RELEASING.md](RELEASING.md).

## License

MIT — see [LICENSE](LICENSE).
