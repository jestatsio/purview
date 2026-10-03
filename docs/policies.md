# Writing policies

A `Policy` maps a model and action to synchronous Python functions. Each function
returns SQLAlchemy boolean predicates. Purview combines those predicates and lets
the database evaluate them.

The snippets below build on the models and session setup in the
[quickstart](quickstart.md).

## Grant access with predicates

```python
from sqlalchemy import true
from purview import READ, Context, Policy

policy = Policy()


@policy.rule(Post, READ)
def read_posts(ctx: Context):
    predicates = []
    if ctx.has_role("author"):
        predicates.append(Post.author_id == ctx.user_id)
    if ctx.has_role("admin"):
        predicates.append(true())
    return predicates
```

The predicates are **OR-combined**, including contributions from multiple rules for
the same model and action. An author sees their own posts. An admin sees every post
in the bound tenant. Returning `true()` does not remove the tenant filter.

Returning `[]` or `[false()]` from every registered rule denies access. A rule is a
grant, so adding a restrictive rule alongside a permissive one does not narrow the
permissive rule. To require two conditions, combine them inside one predicate:

```python
from sqlalchemy import and_


@policy.rule(Post, "update")
def update_posts(ctx: Context):
    return [and_(Post.author_id == ctx.user_id, Post.title != "Locked")]
```

Rules should be deterministic expression builders. Resolve identity, membership,
and other external data before binding the context. Do not execute queries or
perform I/O inside a rule.

## Understand the defaults

| Situation | Result |
| --- | --- |
| Read rule exists and returns grants | Matching rows in the current tenant |
| Read rules exist but contribute no grants | No rows |
| No read rule, default `strict=False` | All rows in the current tenant |
| No read rule, `strict=True` | No rows |
| Action has its own rules | Those rules govern the explicit check |
| Action has no rules | Falls back to `read` rules, then the strict-mode default |

The fallback applies to action strings generally, including `update` and `delete`.
For a sensitive custom action, register its rules explicitly. Purview does not
validate action spelling against a fixed list.

Read filtering always uses `READ`. An explicit update rule can differ from the read
rule. It is not automatically intersected with read access, though a handler that
first loads the object through a bound session also requires the object to be readable.

## Check update and delete explicitly

```python
from purview import PurviewForbidden

post = await session.get(Post, post_id)
if post is None:
    raise LookupError("Post not found")
if not await pv.authorize(session, "update", post):
    raise PurviewForbidden("You cannot edit this post")
post.title = "Updated title"
await session.commit()
```

Call the helper before changing the object. Authorization queries can trigger
SQLAlchemy autoflush. The check evaluates stored row values and is not an automatic
validation of the proposed changes.

For deletion, call `authorize(session, "delete", post)` before
`await session.delete(post)`. The flush guard enforces tenant constraints, but it
does not call action rules for you.

For many existing rows, use a single batch check:

```python
allowed_ids = await pv.authorized_ids(session, "update", Post, [1, 2, 3])
```

The returned IDs are the allowed subset, with no promised input ordering. Composite
primary keys use tuples in primary-key order. UUID and other SQLAlchemy-supported
identifier types can be passed directly.

## Validate proposed objects

Create rules operate on a proposed Python object because no stored row exists yet.
Every registered create rule must return true. These rules are **AND-combined**.

```python
@policy.create_rule(Post)
def create_posts(ctx: Context, proposed: Post) -> bool:
    return ctx.has_role("author") and proposed.author_id == ctx.user_id
```

Call validation before adding the object:

```python
from purview import PurviewForbidden

ctx = pv.context(session)
post = Post(author_id=ctx.user_id, title="New draft")
if not pv.validate_create(session, post):
    raise PurviewForbidden("You cannot create this post")
session.add(post)
await session.commit()
```

`validate_create()` also checks that the proposed tenant is unset or matches the
bound tenant. The flush guard stamps an unset tenant ID. Without registered create
rules, validation only checks the proposed tenant. `strict=True` does not change
create validation, and create rules are not automatically executed by `commit()`.

## Configure tenant fields

The default tenant column is `tenant_id`. Set a different application-wide field:

```python
pv = install(Base, policy, tenant_column="org_id", strict=True)
```

Or configure a particular model before installing:

```python
policy.set_tenant_field(Invoice, "workspace_id")
```

All non-global mapped models must expose their configured tenant column.
`install()` raises `UnscopedModel` if one is missing. Import all model modules before
installing so discovery sees them.

For single-table or joined-table inheritance, register rules, create rules, tenant
field overrides, and global markers on the **base mapped model**. The base model
governs its hierarchy. Subclass-specific configuration does not create an additional
policy layer.

## Global models

Explicitly exempt shared reference data or a tenant root from automatic guards:

```python
policy.global_model(Country)
```

Global models have no automatic read policy or tenant filtering, even with
`strict=True`. Registered rules can still be used through explicit authorization
helpers. Those checks apply the row predicate without a tenant predicate. Global
create validation applies registered create rules without checking a tenant field.

Only mark data global when your application intentionally manages access to it
outside the automatic tenant boundary.

## Role hierarchies

```python
policy.role_implies("admin", "editor")
policy.role_implies("editor", "author")
```

An admin then satisfies `ctx.has_role("author")`. Implications are transitive and
cycle-safe. Purview expands roles when binding a context, explaining a policy, and
evaluating the FastAPI route gate. Define the hierarchy before serving requests.

## Predicate helpers

```python
from purview.predicates import in_values, owned_by

owned_by(Post.author_id, ctx)  # Post.author_id == ctx.user_id
in_values(Post.author_id, [42, 57])  # Post.author_id IN (42, 57)
in_values(Post.author_id, [])  # false()
```

`owned_by()` with `user_id=None` creates an `IS NULL` expression. Authenticate the
actor and validate the context before binding if anonymous ownership is not intended.

The built-in context has `user_id`, `tenant_id`, and `roles`. For more attributes,
use a frozen dataclass subclass and resolve those attributes before binding:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TeamContext(Context[int, int]):
    team_ids: frozenset[int] = frozenset()
```

## Explicit filtered statements

If you need a filtered statement outside a bound session:

```python
from purview.sqlalchemy import authorized_select

statement = authorized_select(
    policy,
    ctx,
    Post,
    tenant_column="tenant_id",
    strict=True,
)
```

This helper applies the read and tenant predicates to that model. It does not bind
a session or install read/write guards. For ordinary application reads, use
`select(Post)` with a bound session.

[Inspect your policy with explain and audit →](debugging.md)
