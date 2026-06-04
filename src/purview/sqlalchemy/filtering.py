"""The filter form (explicit).

On a context-bound session the read guard filters every select automatically, so
the idiomatic collection read is simply ``select(Model)``. ``authorized_select``
is for cases where you need the filtered statement explicitly — composing a
subquery, or running off a session that is not context-bound.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select

from purview.core.actions import READ
from purview.core.context import Context
from purview.core.registry import Policy
from purview.sqlalchemy.predicates import row_predicate, tenant_predicate


def authorized_select(
    policy: Policy,
    ctx: Context[Any, Any],
    model: type,
    tenant_column: str,
) -> Select[Any]:
    """A ``select(model)`` narrowed to the rows ``ctx`` may read.

    Applies tenant scope and the read predicate explicitly. On a bound session
    the guard would apply equivalent criteria too; the duplication is harmless.
    """
    return select(model).where(
        tenant_predicate(model, tenant_column, ctx.tenant_id),
        row_predicate(policy, ctx, model, READ),
    )
