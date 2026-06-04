"""The policy registry.

Policy is split into DATA and CODE. Role assignments and role-to-permission
grants are DATA, read from the host application's own models. The mapping from
an actor to row-shaping predicates is CODE: decorator-registered functions kept
here, so they are type-checked and unit-testable.

This module is pure: it stores callables and model markers and has no knowledge
of sessions, engines, or the web layer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from purview.core.types import RuleFn


class Policy:
    """A registry of authorization rules plus tenant-scoping configuration.

    Rules are keyed by ``(model, action)``. Multiple rules may be registered for
    the same key; their predicates are OR-combined (rules are *granting*).
    """

    def __init__(self) -> None:
        self._rules: dict[tuple[type, str], list[RuleFn]] = {}
        self._global_models: set[type] = set()
        self._tenant_fields: dict[type, str] = {}

    # -- rule registration ------------------------------------------------- #
    def rule(self, model: type, action: str) -> Callable[[RuleFn], RuleFn]:
        """Register a predicate function for ``(model, action)``.

        Used as a decorator::

            @policy.rule(Post, "read")
            def read_post(ctx: Context) -> list[ColumnElement[bool]]:
                rules = []
                if ctx.has_role("author"):
                    rules.append(Post.author_id == ctx.user_id)
                return rules  # OR-combined; empty list = deny
        """

        def decorator(fn: RuleFn) -> RuleFn:
            self._rules.setdefault((model, action), []).append(fn)
            return fn

        return decorator

    def rules_for(self, model: type, action: str) -> list[RuleFn]:
        """All registered rule functions for ``(model, action)`` (possibly empty)."""
        return list(self._rules.get((model, action), ()))

    def has_rules(self, model: type, action: str) -> bool:
        """Whether any rule is registered for ``(model, action)``."""
        return bool(self._rules.get((model, action)))

    # -- tenant scoping configuration -------------------------------------- #
    def global_model(self, model: type) -> type:
        """Mark ``model`` as global (NOT tenant-scoped).

        Secure-by-default: every model is tenant-scoped unless explicitly marked
        global here. Usable as a decorator, returning the class unchanged.
        """
        self._global_models.add(model)
        return model

    def is_global(self, model: type) -> bool:
        """Whether ``model`` has been opted out of tenant scoping."""
        return model in self._global_models

    @property
    def global_models(self) -> frozenset[type]:
        """The set of models opted out of tenant scoping."""
        return frozenset(self._global_models)

    def set_tenant_field(self, model: type, column: str) -> None:
        """Override the tenant column name for ``model`` (default is per-install)."""
        self._tenant_fields[model] = column

    def tenant_field_for(self, model: type, default: str) -> str:
        """The tenant column for ``model``, falling back to the install default."""
        return self._tenant_fields.get(model, default)
