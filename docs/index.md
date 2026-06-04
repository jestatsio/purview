# Purview

**Row-level authorization and multi-tenancy for FastAPI + SQLAlchemy.** Define a
policy once as SQLAlchemy column expressions and get both yes/no checks and query
filtering from the same rule — so the check and the filter can never disagree.

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

That one rule powers a filtered `select(Post)` **and** an
`authorize(session, "read", post)` check.

## Install

```bash
pip install purview-authz            # core + SQLAlchemy
pip install "purview-authz[fastapi]" # plus the FastAPI adapter
```

The distribution is `purview-authz`; the import package is `purview`. Requires
Python 3.11+ and SQLAlchemy 2.0+.

## Quickstart

```python
from sqlalchemy import select, true
from purview import Context, Policy, READ
from purview.sqlalchemy import install

policy = Policy()
policy.global_model(Org)               # opt the tenant root out of scoping

@policy.rule(Post, READ)
def read_post(ctx: Context):
    return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []

pv = install(Base, policy, tenant_column="org_id")   # wires the guards; validates models

async with async_session() as session:
    pv.bind(session, Context(user_id=42, tenant_id=1, roles={"author"}))
    posts = await session.scalars(select(Post))          # filtered automatically
    ok    = await pv.authorize(session, "update", post)  # yes/no for one object
```

## Core ideas

- **One definition, two forms.** A boolean `ColumnElement` filters a collection
  (`.where`) and checks one object (`EXISTS`). The database evaluates both.
- **Tenancy is the session boundary.** One session, one tenant; reads, writes, and
  attaches are all guarded. See the [threat model](THREAT_MODEL.md).
- **Secure by default.** Every model is tenant-scoped; `install()` refuses to start
  if a model lacks its tenant column.

## Learn more

- [Design](DESIGN.md) — the architecture and the keystone idea.
- [Threat model](THREAT_MODEL.md) — what is and isn't enforced, each guarantee mapped
  to its test.
- [Migrating from Oso](MIGRATING_FROM_OSO.md).
- [API reference](reference.md).
