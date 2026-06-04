# Threat Model

Purview's job is one property: **an actor only ever reads or writes rows in its own
tenant, and only rows its policy permits.** This document states the trust boundary,
what is and isn't enforced, and maps each guarantee to the test that proves it.

## Trust boundary: the session

A request binds exactly one [`Context`](../src/purview/core/context.py) (user +
tenant + roles) to its SQLAlchemy session. **The session is the boundary.** Every
guarantee below assumes:

1. One session per request, bound to one tenant via `pv.bind(session, ctx)`.
2. The application does not hand a session bound to one tenant to another tenant's
   request. (Rebinding to a *different* tenant raises `TenantMismatch`.)
3. Relationships are loaded with `selectinload(...)` / `awaitable_attrs`, not
   implicit lazy access (which raises under async — see below).

## What is enforced

| Guarantee | Mechanism | Proven by |
|-----------|-----------|-----------|
| Collection reads return only in-tenant, policy-permitted rows | `do_orm_execute` read guard applies tenant + read predicate via `with_loader_criteria` | `test_read_filter.py` |
| Relationship loads (lazy + eager) are scoped too | `with_loader_criteria` propagation | `test_relationship_loads.py`, `test_adversarial.py` |
| `session.get()` cannot fetch a foreign row | read guard applies on the get's DB load | `test_get_behavior.py`, `test_adversarial::test_no_leak_via_session_get` |
| Object checks can't confirm a foreign/unauthorised row | `EXISTS (… AND <tenant> AND <predicate>)` | `test_exists_check.py`, `test_adversarial_orm::*` |
| Inserts are stamped with the session's tenant | `before_flush` write guard | `test_before_flush.py` |
| Forged-tenant inserts are refused | `before_attach` guard (at construction) / write guard (after attach) | `test_adversarial::test_no_leak_via_forged_create`, `test_before_flush.py` |
| A row cannot be moved across tenants | `before_flush` dirty scan | `test_adversarial::test_no_leak_via_cross_tenant_update` |
| A foreign object cannot be `add`/`merge`'d into a session | `before_attach` guard | `test_adversarial_orm::test_no_leak_via_{merge,detached_reattach}` |
| `merge()` cannot resurrect a foreign row | read-scoped merge load + write guard at flush | `test_adversarial_orm::test_no_leak_via_merge` |
| A session can't be rebound to another tenant | `TenantMismatch` on `bind` | `test_adversarial_orm::test_rebind_to_different_tenant_raises` |
| A model shipped without a tenant column fails closed | `install()` validation | `test_discovery_validation.py`, `test_per_model_column.py` |
| `bypass` does not leak across concurrent tasks | `ContextVar` scoping | `test_bypass_isolation.py` |

Single-table and joined-table inheritance, composite primary keys, and UUID/non-int
ids are covered by the same guarantees (`test_polymorphic.py`,
`test_adversarial_orm::test_single_table_inheritance_is_tenant_filtered`,
`test_composite_and_uuid.py`).

## What is NOT enforced (the sharp edges)

These are **outside the boundary by design** — know them:

- **Raw SQL and Core `text()`** — Purview shapes ORM statements, not hand-written
  SQL. `session.execute(text("SELECT ..."))` sees every tenant
  (`test_adversarial_orm::test_raw_text_sql_is_not_filtered`). Don't hand-write
  tenant-sensitive SQL.
- **Unbound sessions** — a session with no bound context is not filtered. This is how
  you seed and run migrations; never serve a request on one.
- **`bypass(reason=...)` blocks** — enforcement is intentionally suspended. Keep them
  short, greppable, and out of request paths.
- **Implicit lazy loads under async** — these raise `MissingGreenlet` (they do *not*
  silently leak — `test_adversarial_orm::test_implicit_lazy_load_raises_rather_than_leaking`).
  Use `selectinload` / `awaitable_attrs`.

## Within-tenant default

By default a scoped model with no read rule is visible tenant-wide (tenant isolation
still applies). `install(..., strict=True)` flips this to within-tenant default deny.
The **cross-tenant boundary is enforced identically in both modes** — `strict` only
governs models that have no rule of their own.

## Reporting

Found a way to cross the boundary? See [SECURITY.md](../SECURITY.md). The in-scope
definition there matches this document.
