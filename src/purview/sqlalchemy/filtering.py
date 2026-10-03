"""The filter form (explicit).

On a context-bound session the read guard filters every select automatically, so
the idiomatic collection read is simply ``select(Model)``. ``authorized_select``
is for cases where you need the filtered statement explicitly — composing a
subquery, or running off a session that is not context-bound.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy import Select, select

from purview.core.actions import READ
from purview.core.context import Context
from purview.core.registry import Policy
from purview.sqlalchemy.predicates import row_predicate, scope_predicate


def authorized_select(
    policy: Policy,
    ctx: Context[Any, Any],
    model: type,
    tenant_column: str,
    strict: bool = False,
) -> Select[Any]:
    """A ``select(model)`` narrowed to the rows ``ctx`` may read.

    Applies tenant scope and the read predicate explicitly. On a bound session
    the guard would apply equivalent criteria too; the duplication is harmless.
    """
    ctx = replace(ctx, roles=policy.expand_roles(ctx.roles))
    return select(model).where(
        scope_predicate(policy, ctx, model, tenant_column),
        row_predicate(policy, ctx, model, READ, strict),
    )
