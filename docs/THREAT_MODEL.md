# Security boundary

Purview filters supported ORM reads and guards tenant IDs during normal ORM object
writes. Fine-grained create, update, and delete permissions require **explicit
application checks**. This page describes the assumptions and exclusions behind
those controls.

## The session is the boundary

All automatic enforcement assumes:

1. Your application authenticates the principal and verifies their tenant membership
   and roles before constructing `Context`.
2. Each actor/request receives a fresh session, bound before application data is
   loaded or attached. Never share an `AsyncSession` between concurrent tasks.
3. Models and policy configuration are complete before calling `install()`.
4. Queries and writes use the supported ORM paths described below.
5. The application checks action permissions before mutation, and uses database
   constraints and transaction handling appropriate to its consistency needs.

Rebinding to a different tenant raises `TenantMismatch`. Rebinding within the same
tenant is allowed, but it does **not** clear loaded objects or retroactively revoke
access. SQLAlchemy's identity map can return an already-loaded object without a
query. Treat an actor or role change as a reason to open a new session.

## Automatic enforcement

The test links below map the behavior to repository evidence. They describe the
tested paths, rather than a claim about every possible SQLAlchemy operation.

| Behavior | Mechanism | Tests |
| --- | --- | --- |
| Collection reads are narrowed to tenant and read policy | `do_orm_execute` with `with_loader_criteria` | [Read filtering](https://github.com/jestatsio/purview/blob/main/tests/integration/test_read_filter.py) |
| Supported relationship loads are filtered | Criteria applied to eager and lazy load statements | [Relationship loads](https://github.com/jestatsio/purview/blob/main/tests/integration/test_relationship_loads.py) |
| `session.get()` database loads obey read criteria | Read guard on the database query | [Get behavior](https://github.com/jestatsio/purview/blob/main/tests/integration/test_get_behavior.py) |
| New objects with no tenant ID receive the bound tenant | `before_flush` guard | [Flush guards](https://github.com/jestatsio/purview/blob/main/tests/integration/test_before_flush.py) |
| Foreign tenant IDs are rejected on object attachment or insert | `before_attach` and `before_flush` guards | [Adversarial writes](https://github.com/jestatsio/purview/blob/main/tests/integration/test_adversarial.py) |
| Dirty objects cannot change their tenant away from the bound tenant | `before_flush` dirty-object check | [Write guard edges](https://github.com/jestatsio/purview/blob/main/tests/integration/test_write_guard_edges.py) |
| Detached cross-tenant objects cannot be added through supported paths | Attach guard and merge/flush handling | [Adversarial ORM paths](https://github.com/jestatsio/purview/blob/main/tests/integration/test_adversarial_orm.py) |
| Rebinding to another tenant is rejected | `TenantMismatch` | [Rebinding tests](https://github.com/jestatsio/purview/blob/main/tests/integration/test_adversarial_orm.py) |
| Missing tenant fields fail during installation | Mapper discovery and validation | [Discovery validation](https://github.com/jestatsio/purview/blob/main/tests/integration/test_discovery_validation.py) |

With asynchronous sessions, use `selectinload(...)` or
`AsyncAttrs.awaitable_attrs` for relationships. Implicit lazy access that requires
I/O can raise SQLAlchemy's `MissingGreenlet` error.

Single-table and joined-table inheritance, composite keys, and UUID keys have
dedicated coverage in [polymorphic tests](https://github.com/jestatsio/purview/blob/main/tests/integration/test_polymorphic.py)
and [key tests](https://github.com/jestatsio/purview/blob/main/tests/integration/test_composite_and_uuid.py).
Configure inherited policies on the base mapped model.

## Checks your application must call

| Operation | Required call | What it checks |
| --- | --- | --- |
| Update an existing object | `await pv.authorize(session, "update", obj)` | Existing primary key, tenant, and governing action predicate |
| Delete an existing object | `await pv.authorize(session, "delete", obj)` | Existing primary key, tenant, and governing action predicate |
| Validate a proposed object | `pv.validate_create(session, obj)` | Proposed tenant and all registered create rules |
| Check multiple IDs | `await pv.authorized_ids(session, action, Model, ids)` | Allowed subset using the same action predicate |

Call checks **before modifying objects**. Authorization queries can trigger
autoflush, and checks evaluate stored row values rather than validating every
proposed field change. Use database transactions, locks, constraints, or additional
application validation where concurrent changes matter. Purview does not make a
separate check and later write atomic by itself.

The ordinary flush guard handles tenant constraints, not the above fine-grained
action rules. In particular, registering a create rule does not cause a flush to
evaluate it.

Checks are covered by [EXISTS tests](https://github.com/jestatsio/purview/blob/main/tests/integration/test_exists_check.py),
[create-rule tests](https://github.com/jestatsio/purview/blob/main/tests/integration/test_create_rules.py),
and [authorization regressions](https://github.com/jestatsio/purview/blob/main/tests/integration/test_authorization_regressions.py).
The regression suite includes preserving flush guards and nested reads during
authorization-query autoflush.

## Outside automatic enforcement

| Path | Boundary |
| --- | --- |
| Raw SQL, `text()`, SQLAlchemy Core tables, direct connections | No automatic tenant or policy filtering |
| Bulk `INSERT`, `UPDATE`, or `DELETE`, including `session.execute(update(Model))` | Bypasses object-level flush checks and is not automatically scoped |
| Unbound sessions | No automatic filtering or tenant checks |
| Explicit `bypass(reason=...)` blocks | Automatic guards are suspended |
| Models marked global | No automatic tenant or row filtering, even in strict mode |
| Objects already in memory or loaded before binding | No retroactive filtering or revocation |
| Database cascades, triggers, and external writers | Enforced by your database and application design |
| Field-level permissions | Enforced by input validation and serialization |

Opt-in `warn_on_unfiltered=True` emits advisory warnings for recognized unfiltered
operations. It does not block them and is not an exhaustive detector of unsupported
paths.

The bypass uses a `ContextVar` and resets on exit. Independently created request
tasks remain isolated, as exercised by
[bypass isolation tests](https://github.com/jestatsio/purview/blob/main/tests/integration/test_bypass_isolation.py).
Child tasks created inside a bypass block inherit that context, so do not start
ordinary request work there. Use a dedicated maintenance session and do not reuse
its loaded objects in a request.

## Default visibility

A scoped model with no read rule is tenant-wide by default. `strict=True` changes
that to default deny. A registered read rule that contributes no granting predicates
denies access in either mode. An action without its own rules falls back to `read`.

`pv.audit()` and `install(audit="warn" | "raise")` surface tenant-wide models.
Auditing does not prove that a registered rule is sufficiently restrictive. Review
policy logic and test realistic actors against representative data.

## Database integrity

Purview is an application-layer control. Tenant-aware foreign keys, unique
constraints, and database row-level security can provide additional protections.
Purview does not validate arbitrary relationship assignments or automatically
create tenant-aware schema constraints.

## Report a vulnerability

See the [security policy](https://github.com/jestatsio/purview/blob/main/SECURITY.md)
for private reporting. Include a minimal reproduction, the query or write path,
session binding order, model definitions, and installed versions.
