# Purview — Design

Purview is a row-level authorization and multi-tenancy layer for **FastAPI +
SQLAlchemy 2.0 (async-first)**. You define each policy once as a SQLAlchemy
column expression. That single definition answers both *"can this actor do this
to this object?"* (yes/no) and *"which rows can this actor see?"* (a `WHERE`
clause). One source of truth, so the check and the filter cannot disagree —
drift between them is a data leak.

## The keystone: policy as column expressions

A rule returns SQLAlchemy boolean predicates (e.g. `Post.author_id == ctx.user_id`).
A `ColumnElement` is bidirectional:

- **Filter form** — applied with `.where(...)` to shape a collection read into SQL.
- **Check form** — the same predicate scoped to one row as
  `EXISTS (SELECT 1 FROM t WHERE pk = :id AND <predicate>)`, evaluated with
  `.scalar()`. The **database** evaluates it, so relationship/join predicates work
  correctly and there is no in-Python re-implementation of SQL semantics.

Because both forms come from one definition, they cannot drift.

## Roles select predicates

The actor's tenant-scoped roles decide which predicates apply for a given
`(action, resource type)`. Granting predicates are **OR-combined**. No granting
role yields an empty set, which compiles to `false()` — **default deny**.

**Role hierarchies.** `Policy.role_implies("admin", "editor")` declares that a
higher role also grants lower ones (transitively, cycle-safe). The closure is
expanded **once at `bind`**, where the policy is in scope, and stored on the
session's context — so rules keep calling `ctx.has_role("editor")` unchanged and an
`admin` satisfies it. Expansion deliberately does not live on `Context` (which stays
frozen and policy-agnostic) nor in an author-called helper (which could be forgotten,
a silent authz gap); doing it at the single `bind` entry point makes it transparent
and secure-by-default.

## Tenancy is the session boundary

Tenant isolation does not live in a per-query filter you hope always runs:

- One session per request, bound to exactly one tenant (in `session.info`).
  Rebinding it to a *different* tenant raises `TenantMismatch`.
- A `do_orm_execute` hook applies the tenant filter via `with_loader_criteria`,
  scoping every read to the session's bound tenant.
- A `before_flush` hook auto-populates the tenant column on inserts and rejects
  dirty objects whose tenant does not match — closing the write path.

Fine-grained read predicates ride the same `do_orm_execute` hook, which scopes
relationship loads (lazy and eager) as well as top-level selects.

**Secure by default:** every mapped model is tenant-scoped automatically. A model
is opted out only by an explicit `global_model` marker, and `install()` *raises*
if a non-global model lacks a resolvable tenant column — so a model that would
ship unscoped is rejected at startup rather than leaking at query time.

## Layering

- `core` — `Context`, the rule registry, predicate combination. No web or
  ORM-execution imports; unit-testable with zero database.
- `sqlalchemy` — session hooks, query building, the EXISTS check, the bypass
  context manager, tenant binding.
- `fastapi` — dependencies that resolve `Context` and call `authorize`, plus 403
  handling.

## Introspection, without a database

`Purview.explain(session_or_ctx, action, model)` compiles the exact tenant + row
predicate the guard would apply — reusing the same `predicates.row_predicate` /
`tenant_predicate` the read guard and the EXISTS check use, so the explanation can
never drift from enforcement. It builds and compiles expressions but never executes
them, so it needs no session round-trip and no async. `Purview.audit()` classifies
every model's read visibility from the policy alone, flagging scoped models with no
read rule (visible tenant-wide under the default policy); `install(audit="warn"|
"raise")` surfaces those at startup, the same fail-closed posture as the unscoped-model
check. Both are pure developer aids — they observe the policy, they do not change it.

## Escape hatch

One loud, greppable bypass for admin tooling and migrations:

```python
with policy.bypass(reason="nightly billing rollup"):
    ...
```

Raw SQL and Core `text()` are outside the enforcement boundary by documentation.
`install(warn_on_unfiltered=True)` turns that documentation into a runtime
`PurviewWarning` (raw `text()` on a bound session, or any query on an unbound one) —
an advisory aid for development, not an enforcement control.

---

## Phase-0 spike findings (empirical basis)

Before any library code was written, a throwaway spike validated the riskiest
SQLAlchemy behaviors on `aiosqlite` (the mechanisms behave identically to
Postgres for these questions). All gating experiments passed — **GO**.

| Area | Result | Consequence |
|------|--------|-------------|
| `session.get()` on identity-map **miss** | Filters correctly → returns `None` for a foreign-tenant row | **No `tenant_get()` wrapper needed**; `session.get()` is safe |
| `session.get()` with criteria active | Declines the identity-map shortcut and re-queries | Re-validates tenant in SQL on every get — stronger than "the map can't hold a foreign row" |
| `with_loader_criteria` → top-level / eager (`selectinload`) / lazy loads | All filtered; a planted cross-tenant child is excluded | Read guard applies criteria for every scoped entity on every select (defensive, not propagation-only) |
| Direct sync lazy access under async | Raises `MissingGreenlet` | **Forbid implicit lazy loads**; require `selectinload` / `AsyncAttrs.awaitable_attrs` |
| EXISTS check (ownership / join / batch) | Correct in all three forms | **Drop the in-Python evaluator**; the DB evaluates joins. Batch form (id-set) avoids N+1 |
| `before_flush` (auto-populate / forged insert / cross-tenant move) | Auto-populates; raises on forged insert and cross-tenant move | Write path closed; distinct from the read guard |
| `with_loader_criteria` + joined-table inheritance | `select(Dog)` / `select(Animal)` filtered | **Polymorphic / joined inheritance supported in v1** |
| Events on the sync `Session` under `AsyncSession` | Fire correctly | Register hooks on `sqlalchemy.orm.Session` |
| Secure-by-default mapper enumeration | Scoped set resolved; an unscoped non-global model is detected at config time | `install()` fails closed on an unscoped model |

Deferred to the real test suite: Postgres fidelity, `bypass()` semantics,
single-table inheritance, performance benchmarking.
