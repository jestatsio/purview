# Design

Purview keeps row permissions in SQLAlchemy expressions. A single rule definition
can shape a collection query and answer an explicit object permission check. This
avoids maintaining a SQL filter and a separate Python implementation of the same
condition.

## Policy as SQL expressions

A rule returns boolean predicates such as `Post.author_id == ctx.user_id`.
Granting predicates are OR-combined, then composed with the structural tenant
predicate for scoped models.

- **Filter form:** add predicates to an ORM read using `with_loader_criteria`.
- **Check form:** query `EXISTS` for a primary key plus tenant and action predicates.
- **Batch form:** select the allowed subset of candidate primary keys in one query.

The database evaluates these expressions. Relationship predicates can use normal
SQLAlchemy constructs such as `.has()` and `.any()`. Policy authors remain
responsible for building expressions that correctly reflect their domain.

Read filtering always uses the read rule. Explicit action checks use that action's
rules when present, otherwise they fall back to read. The predicates share an
implementation, while the action and statement shape remain explicit inputs.

## Separate tenant scope from row policy

Tenant scope and row policy solve different problems:

| Layer | Responsibility |
| --- | --- |
| Tenant scope | Match the bound tenant on every supported scoped read |
| Read policy | Narrow which rows within the tenant an actor can read |
| Explicit action check | Decide whether an actor may perform an action on an existing row |
| Create validation | Check the proposed tenant and registered Python create predicates |
| Flush and attach guards | Stamp or reject tenant IDs on ordinary ORM object writes |

By default, a scoped model with no read rule is tenant-wide. `strict=True` denies
that model instead. A registered rule with no grants always denies.

Every mapped model discovered under the configured base needs its tenant field
unless explicitly marked global. A missing field causes `install()` to raise
`UnscopedModel`. The global marker exempts that model from automatic guards.

## Session lifecycle

`pv.bind(session, context)` stores the context in `session.info`. An `AsyncSession`
and its underlying synchronous session share this information. SQLAlchemy's
synchronous session events therefore see the context bound by asynchronous code.

One fresh session belongs to one actor/request. Binding happens before loading
application data. A different tenant cannot be rebound onto the same session.
Within-tenant rebinding is possible, but the identity map retains loaded objects,
so applications should open a new session when actor permissions change.

Install the enforcer once after registering models and policies. The default event
target is SQLAlchemy's `Session` class. Applications with multiple independent
enforcers can use dedicated synchronous session subclasses with matching async
session configuration and pass each class through `session_class=`.

## Read and write hooks

The `do_orm_execute` hook attaches tenant and read criteria to ORM selects using
`with_loader_criteria(..., include_aliases=True)`. Criteria are applied for each
discovered scoped entity, including relationship load statements. A criterion for
an entity absent from the statement does not add that entity to the query.

The `before_attach` hook rejects objects carrying a foreign tenant ID. The
`before_flush` hook stamps missing tenant IDs on new objects, refuses forged insert
tenants, and rejects dirty objects whose tenant differs from the bound context.
These guards do not evaluate fine-grained action or create rules.

Explicit authorization queries contain their own predicates. An internal
statement-level marker avoids adding automatic read criteria to those queries.
Flush guards and any nested reads triggered during autoflush remain active.

Bulk DML and direct SQL do not take the same paths. See the
[security boundary](THREAT_MODEL.md) for the full list of exclusions.

## Model inheritance and identifiers

Single-table and joined-table hierarchies use the base mapper's policy
configuration. Register rules, create rules, tenant field overrides, and global
markers on the base mapped model. This keeps automatic read filtering and explicit
checks aligned for subclass instances.

Object checks inspect the model's actual primary-key mapping. Batch checks support
both scalar and composite keys and preserve the requested model's subclass scope.
They do not require integer identifiers.

## Role hierarchies

`policy.role_implies("admin", "editor")` declares a transitive implication.
Expansion is cycle-safe and happens at binding. The FastAPI route gate, explicit
filtered statement builder, and explanation helper also expand roles when they
accept a bare context.

`Context` remains a frozen data object. It does not load roles or know about a
policy registry. Authentication and tenant membership resolution stay in the host
application.

## Package layers

| Package | Responsibility |
| --- | --- |
| `purview.core` | Context, registry, expression combination, audit and explanation data |
| `purview.sqlalchemy` | Model discovery, session hooks, filtering, checks, and bypass |
| `purview.fastapi` | Context-binding dependencies, route and object guards, HTTP errors |
| `purview.predicates` | Convenience imports for common expression builders |

The FastAPI adapter is optional. The core owns no database schema, migrations,
membership tables, or authentication system.

## Introspection

`pv.explain()` reuses the predicate builders and compiles their output for inspection.
It includes the governing action and each rule's contribution. `pv.audit()`
classifies discovered model visibility. Neither tool queries the database.

Audit mode can warn or raise for scoped models with no read rule when those models
would be tenant-wide. Warnings about unfiltered operations are also opt-in. These
tools expose configuration, and do not extend the enforcement boundary.

## Design evidence

Early exploratory work examined SQLAlchemy loader criteria, async session events,
inheritance, and primary-key checks before the library was built. The maintained
integration suite now exercises these mechanisms on SQLite and, when configured,
PostgreSQL.

One crucial distinction from early experiments: `session.get()` can reuse a cached
object. The read guard applies when a database query is issued, not to arbitrary
objects already in memory. Fresh bound sessions are part of the supported lifecycle.

The [security boundary](THREAT_MODEL.md) links individual behavior to its regression
coverage. [Contributing](https://github.com/jestatsio/purview/blob/main/CONTRIBUTING.md)
explains how to run the suites.
