# API reference

The public API, generated directly from source docstrings. Start with
[installation](installation.md) and the [quickstart](quickstart.md) for a runnable
setup, or see [writing policies](policies.md) for action semantics.

Import the core types from `purview`, the enforcement adapter from
`purview.sqlalchemy`, and the optional web adapter from `purview.fastapi`.

| Task | API |
| --- | --- |
| Register read or action rules | `Policy.rule()` |
| Register proposed-object checks | `Policy.create_rule()` |
| Install and bind session guards | `install()`, `Purview.bind()` |
| Check an existing row or ID set | `Purview.authorize()`, `Purview.authorized_ids()` |
| Validate a proposed object | `Purview.validate_create()` |
| Inspect policy behavior | `Purview.explain()`, `Purview.audit()` |
| Bind a FastAPI request | `context_binder()` |

`READ`, `CREATE`, `UPDATE`, and `DELETE` are string action constants. Action checks
without registered rules fall back to `READ`. Create rules use the separate
`create_rule()` / `validate_create()` API.

## Core

::: purview.Policy

::: purview.Context

## Enforcement (`purview.sqlalchemy`)

::: purview.sqlalchemy.install

::: purview.sqlalchemy.Purview

::: purview.sqlalchemy.authorized_select

::: purview.sqlalchemy.bypass

## Predicate helpers (`purview.predicates`)

::: purview.predicates.owned_by

::: purview.predicates.in_values

## Introspection

::: purview.PredicateExplanation

::: purview.RuleContribution

::: purview.AuditReport

::: purview.ModelAudit

## FastAPI (`purview.fastapi`)

::: purview.fastapi.context_binder

::: purview.fastapi.requires

::: purview.fastapi.authorize_or_403

::: purview.fastapi.install_error_handlers

## Exceptions

::: purview.PurviewError

::: purview.PurviewForbidden

::: purview.CrossTenantWrite

::: purview.TenantMismatch

::: purview.UnscopedModel

::: purview.PolicyAuditError

::: purview.PurviewWarning
