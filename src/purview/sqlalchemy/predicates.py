"""Predicate assembly shared by the read guard, the EXISTS check, and filtering.

Two layers compose, both fail-safe at the tenant boundary:

* **Tenant scope** (structural, always applied to scoped models): ``<tenant> == ctx.tenant_id``.
* **Row predicate** (opt-in narrowing): the OR-combined rules for the governing
  action. ``update``/``delete`` fall back to the ``read`` rule set unless a
  stricter rule is registered for them. A model with *no* rule for the governing
  action is row-open (``true()``) — tenant isolation still applies.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, false, true

from purview.core.actions import READ
from purview.core.combine import evaluate_predicate
from purview.core.context import Context
from purview.core.registry import Policy

_FALSE_TYPE = type(false())


def governing_action(policy: Policy, model: type, action: str) -> str:
    """The action whose rules govern ``action`` — itself if it has rules, else READ."""
    return action if policy.has_rules(model, action) else READ


def row_predicate(
    policy: Policy,
    ctx: Context[Any, Any],
    model: type,
    action: str,
) -> ColumnElement[bool]:
    """The fine-grained predicate for ``(model, action)`` (``true()`` if unruled)."""
    gov = governing_action(policy, model, action)
    if policy.has_rules(model, gov):
        return evaluate_predicate(policy, ctx, model, gov)
    return true()


def tenant_predicate(
    model: type,
    tenant_column: str,
    tenant_id: Any,
) -> ColumnElement[bool]:
    """The structural tenant-scope predicate ``model.<tenant_column> == tenant_id``."""
    predicate: ColumnElement[bool] = getattr(model, tenant_column) == tenant_id
    return predicate


def grants(policy: Policy, ctx: Context[Any, Any], model: type, action: str) -> bool:
    """Whether ``ctx`` has any standing grant for ``(model, action)``.

    True unless the row predicate is statically ``false()`` (no granting role). A
    coarse gate for route guards — it does not consider tenant scope or specific
    rows, only whether the actor could ever be permitted.
    """
    return not isinstance(row_predicate(policy, ctx, model, action), _FALSE_TYPE)
