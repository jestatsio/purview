"""Shared type aliases for the core layer."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement

if TYPE_CHECKING:
    from purview.core.context import Context

# A rule maps an actor Context to zero or more boolean predicates. The predicates
# are OR-combined; returning an empty list denies (see ``evaluate_predicate``).
RuleFn = Callable[["Context[Any, Any]"], list[ColumnElement[bool]]]

# A create rule maps (Context, the proposed instance) to a boolean — create has no
# row to filter, so it is a plain predicate over the not-yet-persisted object.
CreateRuleFn = Callable[["Context[Any, Any]", Any], bool]
