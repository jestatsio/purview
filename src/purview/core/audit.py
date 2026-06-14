"""Policy audit — surface scoped models that are visible tenant-wide.

A scoped model with no ``read`` rule is, under the default (non-strict) within-tenant
policy, readable by *every* actor in its tenant. That is sometimes intended and
sometimes an accident. :func:`build_audit` classifies every model so the gap is
visible at startup rather than discovered in production. Pure: it inspects the policy
only, no session and no database.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from purview.core.actions import READ
from purview.core.registry import Policy

# Visibility classifications.
GLOBAL = "global"
RULED = "ruled"
TENANT_WIDE = "tenant-wide"
DEFAULT_DENY = "default-deny"


@dataclass(frozen=True)
class ModelAudit:
    """The read-visibility classification of one model."""

    model: str
    tenant_scoped: bool
    tenant_column: str | None
    has_read_rule: bool
    visibility: str


@dataclass(frozen=True)
class AuditReport:
    """The visibility classification of every discovered model."""

    strict: bool
    tenant_column: str
    models: tuple[ModelAudit, ...]

    @property
    def tenant_wide_models(self) -> tuple[ModelAudit, ...]:
        """Scoped models readable by every actor in their tenant (no read rule)."""
        return tuple(m for m in self.models if m.visibility == TENANT_WIDE)

    def __str__(self) -> str:
        lines = [f"Purview policy audit (strict={self.strict})"]
        for m in self.models:
            scope = m.tenant_column if m.tenant_scoped else "global"
            lines.append(f"  {m.model:<24} {m.visibility:<13} ({scope})")
        flagged = self.tenant_wide_models
        if flagged:
            names = ", ".join(m.model for m in flagged)
            lines.append(f"  → tenant-wide visible (no read rule): {names}")
        return "\n".join(lines)


def build_audit(
    policy: Policy,
    scoped: Iterable[type],
    global_models: Iterable[type],
    tenant_column: str,
    strict: bool = False,
) -> AuditReport:
    """Classify the read visibility of every scoped and global model."""
    models: list[ModelAudit] = []

    for model in scoped:
        has_rule = policy.has_rules(model, READ)
        visibility = RULED if has_rule else DEFAULT_DENY if strict else TENANT_WIDE
        models.append(
            ModelAudit(
                model=model.__name__,
                tenant_scoped=True,
                tenant_column=policy.tenant_field_for(model, tenant_column),
                has_read_rule=has_rule,
                visibility=visibility,
            )
        )

    for model in global_models:
        models.append(
            ModelAudit(
                model=model.__name__,
                tenant_scoped=False,
                tenant_column=None,
                has_read_rule=policy.has_rules(model, READ),
                visibility=GLOBAL,
            )
        )

    models.sort(key=lambda m: m.model)
    return AuditReport(strict=strict, tenant_column=tenant_column, models=tuple(models))
