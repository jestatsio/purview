"""Predicate introspection types — the shape of an ``explain()`` result.

These are plain, pure dataclasses describing what the guard would apply for a
``(model, action)`` under a context: the compiled tenant + row SQL and a per-rule
breakdown. The builder that fills them in by reusing the engine's predicate helpers
lives in :mod:`purview.sqlalchemy.explanation`, so the pure core stays free of the
engine. Nothing here executes SQL — it only compiles expressions to strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement


def compile_predicate(expr: ColumnElement[Any]) -> str:
    """Compile ``expr`` to a literal-bound SQL string (best effort).

    Falls back to ``str(expr)`` when a bind value cannot render as a literal — this
    is a developer aid, not executed SQL, so a readable approximation is fine.
    """
    try:
        return str(expr.compile(compile_kwargs={"literal_binds": True}))
    except Exception:  # pragma: no cover - exotic bind types only
        return str(expr)


@dataclass(frozen=True)
class RuleContribution:
    """One registered rule's contribution to the combined row predicate."""

    rule_name: str
    branch_count: int
    predicate_sql: str | None


@dataclass(frozen=True)
class PredicateExplanation:
    """What the guard would apply for one ``(model, action)`` under one context."""

    model: str
    action: str
    governing_action: str
    active_roles: frozenset[str]
    tenant_scoped: bool
    tenant_column: str | None
    tenant_sql: str | None
    row_sql: str
    combined_sql: str
    contributions: tuple[RuleContribution, ...]
    is_default_deny: bool
    strict: bool

    def __str__(self) -> str:
        lines = [f"Purview.explain({self.model}, {self.action!r})"]
        if self.action != self.governing_action:
            lines.append(
                f"  governed by   : {self.governing_action!r} "
                f"({self.action!r} falls back to it — no own rule)"
            )
        roles = ", ".join(sorted(self.active_roles)) or "(none)"
        lines.append(f"  active roles  : {roles}")
        if self.tenant_scoped:
            lines.append(f"  tenant scope  : {self.tenant_sql}")
        else:
            lines.append("  tenant scope  : (global model — not tenant-scoped)")
        lines.append(f"  row predicate : {self.row_sql}")
        if self.is_default_deny:
            lines.append("                  → default deny (no granting rule)")
        lines.append(f"  combined      : {self.combined_sql}")
        if self.contributions:
            lines.append("  rules:")
            for c in self.contributions:
                if c.predicate_sql is None:
                    lines.append(f"    - {c.rule_name}: contributed nothing")
                else:
                    lines.append(f"    - {c.rule_name}: {c.predicate_sql}")
        return "\n".join(lines)
