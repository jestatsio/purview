"""Predicate combination — the security heart.

A single boolean expression is derived from the registered rules and used two
ways that cannot drift:

* **Filter form** — applied with ``.where(...)`` to shape a collection read.
* **Check form** — wrapped in ``EXISTS (SELECT 1 ... AND <predicate>)`` to answer
  yes/no for one object.

Granting predicates are OR-combined. An empty set compiles to ``false()`` —
**default deny**.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, false, or_

if TYPE_CHECKING:
    from purview.core.context import Context
    from purview.core.registry import Policy


def evaluate_predicate(
    policy: Policy,
    ctx: Context[Any, Any],
    model: type,
    action: str,
) -> ColumnElement[bool]:
    """Combine all granting predicates for ``(model, action)`` into one boolean.

    Returns ``false()`` when no rule grants anything, so the absence of a
    granting role is a denial, never an accident.
    """
    predicates: list[ColumnElement[bool]] = []
    for fn in policy.rules_for(model, action):
        predicates.extend(fn(ctx))

    if not predicates:
        return false()
    first, *rest = predicates
    if not rest:
        return first
    return or_(first, *rest)
