# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Docs**: a [threat model](docs/THREAT_MODEL.md) (each guarantee mapped to its
  test) and a [migrating-from-Oso guide](docs/MIGRATING_FROM_OSO.md).
- **Fine-grained `create` rules**: `@policy.create_rule(Model)` runs a plain
  `(ctx, proposed_obj) -> bool` predicate at `validate_create` time — create has no
  row to filter, so it is a type-checked Python predicate over the proposed object.
  Multiple rules AND-combine; the tenant check and the flush-time write guard still
  apply.
- **Composite primary keys** in `batch_check` / `authorized_ids` (matching on the
  tuple of key columns; single-column keys are unchanged). Verified UUID / non-int
  tenant and user ids across SQLite and Postgres.
- **Per-model tenant columns**: `Policy.set_tenant_field(Model, column)` scopes that
  model by its own column (inherited by subclasses), alongside models that use the
  `install(tenant_column=...)` default — wired through discovery, the read/write/
  attach guards, the EXISTS checks, and create validation. Previously the column was
  uniform across every model.
- `before_attach` guard: an object carrying another tenant's id can no longer be
  added or merged into a session bound to a different tenant — closing a
  cross-session re-attach / merge hole and keeping one tenant per session.
- Expanded adversarial suite (SQLite + Postgres): `merge`, `refresh` /
  `populate_existing`, detached re-attach, concurrent async-task bypass isolation,
  single-table inheritance, and the documented raw-SQL / lazy-load boundary.

### Changed

- `TenantMismatch` is now raised when a session bound to one tenant is rebound to a
  *different* one (previously exported but never raised). Rebinding within the same
  tenant is still allowed.

## [0.1.1] - 2026-06-04

### Added

- Official support for **Python 3.14** (added to the CI test matrix; the suite was
  already passing on 3.14).

### Fixed

- Documentation: corrected an overclaim in the design notes — the read guard scopes
  every read to the session's tenant, but does not *assert* tenant equality (no such
  check exists yet; tracked for 0.2 via `TenantMismatch`).

## [0.1.0] - 2026-06-04

### Added

- **Core** (`purview.core`): `Context`, the `Policy` rule registry, and the
  default-deny predicate combinator — framework-agnostic, no ORM-execution imports.
- **SQLAlchemy engine** (`purview.sqlalchemy`): secure-by-default model discovery
  with install-time validation; the `do_orm_execute` read guard (tenant scope +
  fine-grained read predicates, propagating to lazy and eager relationship loads);
  the `before_flush` write guard (tenant auto-stamp, forged-insert and
  cross-tenant-move rejection); single and batch EXISTS checks; explicit
  `authorized_select`; and the `bypass` escape hatch.
- **FastAPI adapter** (`purview.fastapi`): `context_binder`, the `requires` route
  guard, `authorize_or_403`, and a `PurviewForbidden`/`CrossTenantWrite` → 403
  handler.
- `install(..., strict=True)` for within-tenant default deny: a scoped model with
  no read rule denies instead of defaulting to tenant-scope-only.
- Test suite: unit (100% branch coverage on the combinator), integration
  (parametrized over SQLite and Postgres), an adversarial leak suite, and a
  runnable FastAPI example app.

[Unreleased]: https://github.com/jestatsio/purview/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/jestatsio/purview/releases/tag/v0.1.1
[0.1.0]: https://github.com/jestatsio/purview/releases/tag/v0.1.0
