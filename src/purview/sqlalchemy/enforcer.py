"""The enforcer facade and ``install`` entry point.

``Purview`` carries the policy and tenant configuration and wires the read/write
guards onto a session class. Once installed and a session is bound to a context,
collection reads filter automatically and the check/create helpers share the same
single policy definition.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import Any, Literal

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState, Session

from purview.core.audit import AuditReport, build_audit
from purview.core.context import Context
from purview.core.explanation import PredicateExplanation
from purview.core.registry import Policy
from purview.exceptions import PolicyAuditError, PurviewError, PurviewWarning
from purview.sqlalchemy.binding import bind_context, context_of
from purview.sqlalchemy.bypass import bypass
from purview.sqlalchemy.checking import batch_check, exists_check
from purview.sqlalchemy.creating import validate_create as _validate_create
from purview.sqlalchemy.discovery import discover_scoped
from purview.sqlalchemy.explanation import build_explanation
from purview.sqlalchemy.read_guard import make_read_guard
from purview.sqlalchemy.write_guard import make_attach_guard, make_write_guard

_SessionLike = AsyncSession | Session
_AuditMode = Literal["off", "warn", "raise"]


class Purview:
    """Holds a policy + tenant configuration and enforces it on a session class.

    Construct via :func:`install` (which also wires the guards). The same object
    answers object checks, batch checks, and create validation, all derived from
    the one policy.
    """

    bypass = staticmethod(bypass)

    def __init__(
        self,
        policy: Policy,
        base: Any,
        *,
        tenant_column: str = "tenant_id",
        strict: bool = False,
        warn_on_unfiltered: bool = False,
        audit: _AuditMode = "off",
        session_class: type[Session] = Session,
    ) -> None:
        self.policy = policy
        self.tenant_column = tenant_column
        # strict=True denies reads of a scoped model that has no read rule, rather
        # than defaulting it to tenant-scope-only (within-tenant default deny).
        self.strict = strict
        # Opt-in advisory warnings for the documented unfiltered sharp edges.
        self.warn_on_unfiltered = warn_on_unfiltered
        self._audit_mode: _AuditMode = audit
        # Secure-by-default: raises if any non-global model lacks the tenant column.
        self.scoped: list[type] = discover_scoped(base, policy, tenant_column)
        self._session_class = session_class
        self._read: Callable[[ORMExecuteState], None] | None = None
        self._write: Callable[[Session, Any, Any], None] | None = None
        self._attach: Callable[[Session, object], None] | None = None

    def install(self) -> Purview:
        """Wire the read/write/attach guards onto the session class (idempotent)."""
        if self._read is not None:
            return self
        # Audit first: an audit="raise" must fail before any listener is attached,
        # so a rejected install leaves no dangling guards on the session class.
        self._run_audit()
        self._read = make_read_guard(
            self.policy, self.scoped, self.tenant_column, self.strict, self.warn_on_unfiltered
        )
        self._write = make_write_guard(self.policy, self.scoped, self.tenant_column)
        self._attach = make_attach_guard(self.policy, self.tenant_column)
        event.listen(self._session_class, "do_orm_execute", self._read)
        event.listen(self._session_class, "before_flush", self._write)
        event.listen(self._session_class, "before_attach", self._attach)
        return self

    def _run_audit(self) -> None:
        """Apply the install-time audit mode (warn or raise on tenant-wide models)."""
        if self._audit_mode == "off":
            return
        flagged = self.audit().tenant_wide_models
        if not flagged:
            return
        names = ", ".join(m.model for m in flagged)
        message = (
            f"policy audit: scoped models with no read rule are visible tenant-wide: "
            f"{names}. Add a read rule, or install with strict=True for default deny."
        )
        if self._audit_mode == "raise":
            raise PolicyAuditError(message)
        warnings.warn(message, PurviewWarning, stacklevel=2)

    def uninstall(self) -> None:
        """Remove the guards from the session class."""
        if self._read is None or self._write is None or self._attach is None:
            return
        event.remove(self._session_class, "do_orm_execute", self._read)
        event.remove(self._session_class, "before_flush", self._write)
        event.remove(self._session_class, "before_attach", self._attach)
        self._read = None
        self._write = None
        self._attach = None

    def bind(self, session: _SessionLike, ctx: Context[Any, Any]) -> None:
        """Bind ``ctx`` to ``session`` so reads filter and writes are guarded.

        Declared role implications (:meth:`Policy.role_implies`) are expanded once
        here, so every rule, check, and ``explain`` sees the actor's effective roles.
        """
        bind_context(session, self._expand(ctx))

    def context(self, session: _SessionLike) -> Context[Any, Any]:
        """The context bound to ``session`` (raises if the session is unbound)."""
        return self._ctx(session)

    def _expand(self, ctx: Context[Any, Any]) -> Context[Any, Any]:
        """Return ``ctx`` with its roles expanded under the policy's hierarchy."""
        expanded = self.policy.expand_roles(ctx.roles)
        if expanded == ctx.roles:
            return ctx
        return replace(ctx, roles=expanded)

    def explain(
        self,
        session_or_ctx: _SessionLike | Context[Any, Any],
        action: str,
        model: type,
    ) -> PredicateExplanation:
        """Explain the tenant + row predicate for ``(model, action)``.

        Accepts a bound session or a bare :class:`~purview.core.context.Context`.
        Pure introspection — it compiles the predicate the guard would apply and
        never touches the database. Role implications are expanded first.
        """
        ctx = session_or_ctx if isinstance(session_or_ctx, Context) else self._ctx(session_or_ctx)
        return build_explanation(
            self.policy, self._expand(ctx), model, action, self.tenant_column, self.strict
        )

    def audit(self) -> AuditReport:
        """Classify the read visibility of every model (pure, no database access).

        Reports scoped models with no read rule — visible tenant-wide under the
        default policy. See :meth:`AuditReport.tenant_wide_models`.
        """
        return build_audit(
            self.policy,
            self.scoped,
            self.policy.global_models,
            self.tenant_column,
            self.strict,
        )

    async def authorize(self, session: AsyncSession, action: str, resource: object) -> bool:
        """Whether the bound actor may perform ``action`` on ``resource``."""
        return await exists_check(
            session,
            self.policy,
            self._ctx(session),
            action,
            resource,
            self.tenant_column,
            self.strict,
        )

    async def authorized_ids(
        self,
        session: AsyncSession,
        action: str,
        model: type,
        ids: Iterable[Any],
    ) -> list[Any]:
        """The subset of ``ids`` the bound actor may perform ``action`` on."""
        return await batch_check(
            session,
            self.policy,
            self._ctx(session),
            action,
            model,
            ids,
            self.tenant_column,
            self.strict,
        )

    def validate_create(self, session: _SessionLike, resource: object) -> bool:
        """Whether ``resource`` may be created in the bound actor's tenant.

        Checks the proposed tenant and every registered ``create_rule`` for the
        model. The write guard remains the structural backstop at flush.
        """
        column = self.policy.tenant_field_for(type(resource), self.tenant_column)
        rules = self.policy.create_rules_for(type(resource))
        return _validate_create(self._ctx(session), resource, column, rules)

    def _ctx(self, session: _SessionLike) -> Context[Any, Any]:
        ctx = context_of(session)
        if ctx is None:
            raise PurviewError(
                "session is not bound to a Purview context; call .bind(session, ctx) first"
            )
        return ctx


def install(
    base: Any,
    policy: Policy,
    *,
    tenant_column: str = "tenant_id",
    strict: bool = False,
    warn_on_unfiltered: bool = False,
    audit: _AuditMode = "off",
    session_class: type[Session] = Session,
) -> Purview:
    """Discover scoped models, wire the guards, and return the enforcer.

    Set ``strict=True`` to deny reads of a scoped model that has no read rule
    (within-tenant default deny) instead of defaulting it to tenant-scope-only.

    Set ``warn_on_unfiltered=True`` to emit :class:`~purview.exceptions.PurviewWarning`
    for the documented sharp edges: queries on an unbound session and raw/non-ORM
    statements on a bound one. Off by default (no behavior change).

    Set ``audit`` to ``"warn"`` or ``"raise"`` to surface scoped models with no read
    rule (visible tenant-wide) at install time; ``"raise"`` raises
    :class:`~purview.exceptions.PolicyAuditError`. Under ``strict=True`` such models
    deny by default, so the audit finds nothing.

    Raises :class:`~purview.exceptions.UnscopedModel` if a non-global model lacks
    the tenant column.
    """
    return Purview(
        policy,
        base,
        tenant_column=tenant_column,
        strict=strict,
        warn_on_unfiltered=warn_on_unfiltered,
        audit=audit,
        session_class=session_class,
    ).install()
