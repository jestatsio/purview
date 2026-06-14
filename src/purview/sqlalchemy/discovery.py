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
        f"install() expects a DeclarativeBase subclass or a registry; got {type(base).__name__}"
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
        column = policy.tenant_field_for(cls, tenant_column)
        if hasattr(cls, column):
            scoped.append(cls)
        else:
            problems.append(f"{cls.__name__} (expected {column!r})")

    if problems:
        raise UnscopedModel(
            f"models lack their tenant column and are not marked global: "
            f"{sorted(problems)}. Add the column, mark them with "
            f"Policy.global_model(...), register a column with "
            f"Policy.set_tenant_field(...), or choose a different tenant_column."
        )
    return scoped
