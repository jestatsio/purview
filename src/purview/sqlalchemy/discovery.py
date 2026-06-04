"""Secure-by-default model discovery.

Every mapped model is tenant-scoped unless explicitly marked global. This module
enumerates the declarative registry, resolves which models are scoped, and
**raises at install() time** if a non-global model lacks the tenant column — so a
model that would otherwise ship unscoped is rejected at startup (fail closed)
rather than leaking at query time.
"""

from __future__ import annotations

from typing import Any

from purview.core.registry import Policy
from purview.exceptions import UnscopedModel


def _mappers(base: Any) -> Any:
    registry = getattr(base, "registry", None)
    if registry is not None:
        return registry.mappers
    if hasattr(base, "mappers"):
        return base.mappers
    raise TypeError(
        "install() expects a DeclarativeBase subclass or a registry; "
        f"got {type(base).__name__}"
    )


def discover_scoped(base: Any, policy: Policy, tenant_column: str) -> list[type]:
    """Return the base mapped classes that must be tenant-scoped.

    Subclasses (joined/single-table inheritance) are governed by their base
    mapper and skipped here. A non-global model without ``tenant_column`` raises
    :class:`~purview.exceptions.UnscopedModel`.
    """
    scoped: list[type] = []
    problems: list[str] = []
    for mapper in _mappers(base):
        cls = mapper.class_
        if mapper.inherits is not None:
            continue  # subclasses are covered by their base
        if policy.is_global(cls):
            continue
        if hasattr(cls, tenant_column):
            scoped.append(cls)
        else:
            problems.append(cls.__name__)

    if problems:
        raise UnscopedModel(
            f"models lack the tenant column {tenant_column!r} and are not marked "
            f"global: {sorted(problems)}. Add the column, register them with "
            f"Policy.global_model(...), or choose a different tenant_column."
        )
    return scoped
