"""Framework-agnostic core: Context, the rule registry, predicate combination.

This subpackage has no web or ORM-execution imports. It manipulates SQLAlchemy
expression objects only, so it is unit-testable with zero database.
"""

from __future__ import annotations

from purview.core.actions import CREATE, DELETE, READ, UPDATE, Action
from purview.core.combine import evaluate_predicate
from purview.core.context import Context
from purview.core.registry import Policy
from purview.core.types import RuleFn

__all__ = [
    "CREATE",
    "DELETE",
    "READ",
    "UPDATE",
    "Action",
    "Context",
    "Policy",
    "RuleFn",
    "evaluate_predicate",
]
