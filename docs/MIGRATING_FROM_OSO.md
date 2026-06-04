# Migrating from Oso

[Oso](https://www.osohq.com/) deprecated its open-source library in 2023, with no
SQLAlchemy-2.0 / async path. If you used `sqlalchemy-oso` for data filtering, Purview
covers the same ground — the one part that mattered most: **shaping queries so a user
only loads rows they're allowed to see.** The biggest change is that your policy moves
from the Polar DSL into plain Python SQLAlchemy expressions.

## Concept map

| Oso | Purview |
|-----|---------|
| Polar `allow(actor, action, resource)` rules | `@policy.rule(Model, action)` returning `ColumnElement` predicates |
| Multiple `allow` rules (any matches) | Multiple predicates / rules — **OR-combined** |
| `sqlalchemy-oso` list filtering / `authorized_sessionmaker` | A context-bound session — `select(Model)` is filtered automatically |
| `oso.authorize(actor, action, resource)` | `await pv.authorize(session, action, resource)` |
| `oso.authorized_query(actor, action, Model)` | `select(Model)` on a bound session (or `authorized_select(...)`) |
| Roles in Polar / `actor.role` | `ctx.roles` + `ctx.has_role(...)` |
| Resource relationships in Polar | SQLAlchemy relationship predicates (`Model.rel.has(...)`) |

## Rules: Polar → Python

**Oso (Polar):**

```polar
allow(actor: User, "read", post: Post) if
    post.created_by = actor;

allow(actor: User, "read", _post: Post) if
    actor.role = "admin";
```

**Purview:**

```python
from sqlalchemy import true
from purview import Policy, Context, READ

policy = Policy()

@policy.rule(Post, READ)
def read_post(ctx: Context):
    rules = []
    if ctx.user_id is not None:
        rules.append(Post.created_by_id == ctx.user_id)
    if ctx.has_role("admin"):
        rules.append(true())     # the whole tenant
    return rules                 # OR-combined; empty list = deny
```

The predicate is real SQL: it becomes a `WHERE` for collection reads **and** an
`EXISTS` for single-object checks, from one definition.

## Data filtering: the part you came for

**Oso:**

```python
Session = authorized_sessionmaker(get_oso=..., get_user=..., get_action=...)
posts = session.query(Post).all()   # filtered to authorized rows
```

**Purview:**

```python
from purview.sqlalchemy import install
pv = install(Base, policy, tenant_column="tenant_id")

async with async_session() as session:
    pv.bind(session, Context(user_id=42, tenant_id=1, roles={"admin"}))
    posts = await session.scalars(select(Post))   # filtered automatically
```

No special sessionmaker and no per-query call — binding the context makes every read
(including relationship loads) tenant- and policy-scoped.

## Yes/no checks

**Oso:** `oso.authorize(user, "read", post)` (raises `ForbiddenError`).

**Purview:**

```python
if not await pv.authorize(session, "read", post):
    raise PurviewForbidden(...)
# or, in FastAPI:
await authorize_or_403(pv, session, "read", post)
```

## Multi-tenancy

Oso left tenancy to you. Purview makes it structural: every model is tenant-scoped by
default (`install(tenant_column=...)`, or `Policy.set_tenant_field` per model), the
session is bound to one tenant, and `install()` refuses to start if a model lacks its
tenant column. See [the threat model](THREAT_MODEL.md).

## What's deliberately different

- **No DSL.** Policies are Python functions — type-checked, unit-testable, debuggable
  with a debugger, not a separate language.
- **In-process, SQLAlchemy-only.** No policy engine to run; the database is the
  evaluator. The trade-off: Purview targets FastAPI + SQLAlchemy 2.0 async, not every
  framework.
- **`create` is explicit.** There's no row to filter, so create rules are
  `@policy.create_rule(Model)` returning `bool` from `(ctx, proposed_obj)`.

## Not covered

Field-level authorization (Oso allowed attribute-level rules) is out of scope — it
belongs in your serialization layer. Purview is row-level.
