"""Build a :class:`PredicateExplanation` by reusing the engine's predicate helpers.

This lives in the SQLAlchemy layer because it reuses ``predicates.row_predicate`` /
``tenant_predicate`` / ``governing_action`` — the very expressions the read guard and
the EXISTS check apply — so an explanation can never drift from enforcement. It does
not touch a session and never executes SQL.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, and_, or_

from purview.core.context import Context
from purview.core.explanation import (
    PredicateExplanation,
    RuleContribution,
    compile_predicate,
)
from purview.core.registry import Policy
from purview.sqlalchemy.predicates import (
    _FALSE_TYPE,
    governing_action,
    row_predicate,
    tenant_predicate,
)


def build_explanation(
    policy: Policy,
    ctx: Context[Any, Any],
    model: type,
    action: str,
    tenant_column: str,
    strict: bool = False,
) -> PredicateExplanation:
    """Compile the tenant + row predicate (and per-rule breakdown) for inspection."""
    gov = governing_action(policy, model, action)
    is_global = policy.is_global(model)

    row = row_predicate(policy, ctx, model, action, strict)
    row_sql = compile_predicate(row)
    is_default_deny = isinstance(row, _FALSE_TYPE)

    tenant_col: str | None = None
    tenant_sql: str | None = None
    combined: ColumnElement[bool] = row
    if not is_global:
        tenant_col = policy.tenant_field_for(model, tenant_column)
        tenant = tenant_predicate(model, tenant_col, ctx.tenant_id)
        tenant_sql = compile_predicate(tenant)
        combined = and_(tenant, row)

    contributions: list[RuleContribution] = []
    for fn in policy.rules_for(model, gov):
        branches = fn(ctx)
        name = getattr(fn, "__qualname__", repr(fn))
        if not branches:
            contributions.append(RuleContribution(name, 0, None))
            continue
        combined_branch = branches[0] if len(branches) == 1 else or_(*branches)
        contributions.append(
            RuleContribution(name, len(branches), compile_predicate(combined_branch))
        )

    return PredicateExplanation(
        model=model.__name__,
        action=action,
        governing_action=gov,
        active_roles=ctx.roles,
        tenant_scoped=not is_global,
        tenant_column=tenant_col,
        tenant_sql=tenant_sql,
        row_sql=row_sql,
        combined_sql=compile_predicate(combined),
        contributions=tuple(contributions),
        is_default_deny=is_default_deny,
        strict=strict,
    )
