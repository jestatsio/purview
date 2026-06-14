"""Purview — row-level authorization and multi-tenancy for FastAPI + SQLAlchemy.

Define a policy once as SQLAlchemy column expressions and get both yes/no checks
and query filtering from the same rule, so the check and the filter cannot drift.

The SQLAlchemy enforcement engine lives in :mod:`purview.sqlalchemy` and the
FastAPI edge in :mod:`purview.fastapi`; both are imported on demand so the pure
core stays free of those concerns.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from purview.core.actions import CREATE, DELETE, READ, UPDATE, Action
from purview.core.audit import AuditReport, ModelAudit
from purview.core.context import Context
from purview.core.explanation import PredicateExplanation, RuleContribution
from purview.core.helpers import in_values, owned_by
from purview.core.registry import Policy
from purview.exceptions import (
    CrossTenantWrite,
    PolicyAuditError,
    PurviewError,
    PurviewForbidden,
    PurviewWarning,
    TenantMismatch,
    UnscopedModel,
)

try:
    __version__ = version("purview-authz")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0+unknown"

__all__ = [
    "CREATE",
    "DELETE",
    "READ",
    "UPDATE",
    "Action",
    "AuditReport",
    "Context",
    "CrossTenantWrite",
    "ModelAudit",
    "Policy",
    "PolicyAuditError",
    "PredicateExplanation",
    "PurviewError",
    "PurviewForbidden",
    "PurviewWarning",
    "RuleContribution",
    "TenantMismatch",
    "UnscopedModel",
    "__version__",
    "in_values",
    "owned_by",
]
