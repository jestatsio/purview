# Migrating from Oso

If your application uses Polar policies with the open-source `sqlalchemy-oso`
integration, this guide maps common patterns to Purview. The main change is moving
policy expressions into Python and SQLAlchemy. Purview focuses on row-level
authorization and a tenant-bound session lifecycle.

This is a conceptual migration guide, not a drop-in compatibility layer. Test the
same actors, actions, resources, and tenant boundaries before switching enforcement.

## Concept map

| Oso pattern | Purview equivalent |
| --- | --- |
| Polar `allow(actor, action, resource)` | `@policy.rule(Model, action)` returning SQLAlchemy predicates |
| Multiple granting `allow` rules | Multiple OR-combined rules and predicates |
| `authorized_sessionmaker` list filtering | A fresh context-bound session and ordinary ORM `select()` |
| `oso.authorize(...)` | `await pv.authorize(...)`, which returns a boolean |
| Raising on denied authorization | `authorize_or_403(...)` or your own exception handling |
| Authorized resource query | Bound-session read or explicit `authorized_select(...)` |
| Roles attached to an actor | `Context.roles`, `has_role()`, and optional role implications |
| Resource relationships | SQLAlchemy relationship predicates such as `.has()` and `.any()` |

## Translate a rule

A Polar ownership rule with an admin grant might look like:

```polar
allow(actor: User, "read", post: Post) if
    post.created_by = actor;

allow(actor: User, "read", _post: Post) if
    actor.role = "admin";
```

The corresponding Purview rule uses the model's foreign-key column:

```python
from sqlalchemy import true
from purview import READ, Context, Policy

policy = Policy()


@policy.rule(Post, READ)
def read_post(ctx: Context):
    predicates = []
    if ctx.user_id is not None:
        predicates.append(Post.created_by_id == ctx.user_id)
    if ctx.has_role("admin"):
        predicates.append(true())
    return predicates
```

The predicates are OR-combined. The admin grant permits all rows within the bound
tenant, not across tenants. The application's context resolver supplies verified
roles for that tenant.

## Migrate collection reads

```python
from sqlalchemy import select
from purview.sqlalchemy import install

pv = install(Base, policy, tenant_column="tenant_id", strict=True)

async with sessions() as session:
    pv.bind(session, Context(user_id=42, tenant_id=1, roles={"admin"}))
    posts = (await session.scalars(select(Post))).all()
```

This assumes existing models and an async session factory. The
[quickstart](quickstart.md) provides a complete runnable setup.

`strict=True` makes scoped models without read rules deny access. Review this
explicitly during migration. Purview's default without strict mode is tenant-wide
visibility for models with no read rule.

## Migrate object checks

Unlike APIs that raise on a denied check, `pv.authorize()` returns a boolean:

```python
from purview import PurviewForbidden

if not await pv.authorize(session, "update", post):
    raise PurviewForbidden("You cannot edit this post")
```

In FastAPI, `await authorize_or_403(pv, session, "update", post)` raises the Purview
exception for you. Install the adapter's error handlers to return HTTP 403.

Register action rules explicitly when your old policy distinguished read, update,
delete, or a custom action. Purview falls back to read rules when an action has no
rules of its own.

## Account for creation and tenancy

- Create rules use `@policy.create_rule(Model)` and return booleans from the context
  and proposed object. Call `pv.validate_create(session, proposed)` explicitly.
- Multiple create rules are AND-combined, unlike granting row rules.
- Every discovered model needs a tenant field unless explicitly marked global.
- Global models are exempt from automatic read filtering, including read rules.
- Use a fresh session per actor/request and bind it before loading application data.

## Check the scope of your old policy

Field-level permissions need input-validation or serialization logic. Non-SQLAlchemy
resources and arbitrary Python object checks do not map directly to Purview's
database-backed row checks. Raw SQL and bulk DML require separate controls.

See [writing policies](policies.md) for action semantics and the
[security boundary](THREAT_MODEL.md) for supported enforcement paths.
