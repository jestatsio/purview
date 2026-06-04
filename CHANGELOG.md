# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Test suite: unit (100% branch coverage on the combinator), integration
  (parametrized over SQLite and Postgres), an adversarial leak suite, and a
  runnable FastAPI example app.

[Unreleased]: https://github.com/erichare/purview/commits/main
