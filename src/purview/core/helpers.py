"""Reusable predicate builders for common rule patterns.

Rules return ``list[ColumnElement[bool]]``; these helpers build the most common
elements of that list so a policy reads declaratively. They are pure SQLAlchemy
expression builders — no session, no engine — and compose directly into a rule::

    from purview.predicates import owned_by, in_values

    @policy.rule(Post, READ)
    def read_post(ctx):
        rules = [owned_by(Post.author_id, ctx)]
        if ctx.has_role("editor"):
            rules.append(in_values(Post.section_id, ctx.editable_sections))
        return rules
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import ColumnElement, false
from sqlalchemy.orm import InstrumentedAttribute

from purview.core.context import Context


def owned_by(
    column: InstrumentedAttribute[Any],
    ctx: Context[Any, Any],
) -> ColumnElement[bool]:
    """``column == ctx.user_id`` — the canonical "I own this row" predicate.

    Note: an anonymous context (``user_id is None``) yields ``column IS NULL``;
    deny anonymous actors upstream rather than relying on this.
    """
    result: ColumnElement[bool] = column == ctx.user_id
    return result


def in_values(
    column: InstrumentedAttribute[Any],
    values: Iterable[Any],
) -> ColumnElement[bool]:
    """``column IN (values)`` — membership against a precomputed set.

    Use for sets resolved when the context was built (e.g. the team ids an actor
    belongs to). An empty ``values`` compiles to ``false()`` — preserving
    default-deny and avoiding empty-``IN`` dialect warnings.
    """
    vals = list(values)
    if not vals:
        return false()
    result: ColumnElement[bool] = column.in_(vals)
    return result
