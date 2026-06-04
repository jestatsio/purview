"""The enforcer facade and ``install`` entry point.

``Purview`` carries the policy and tenant configuration and wires the read/write
guards onto a session class. Once installed and a session is bound to a context,
collection reads filter automatically and the check/create helpers share the same
single policy definition.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState, Session

from purview.core.context import Context
from purview.core.registry import Policy
from purview.exceptions import PurviewError
from purview.sqlalchemy.binding import bind_context, context_of
from purview.sqlalchemy.bypass import bypass
from purview.sqlalchemy.checking import batch_check, exists_check
from purview.sqlalchemy.creating import validate_create as _validate_create
from purview.sqlalchemy.discovery import discover_scoped
from purview.sqlalchemy.read_guard import make_read_guard
from purview.sqlalchemy.write_guard import make_write_guard

_SessionLike = AsyncSession | Session


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
        session_class: type[Session] = Session,
    ) -> None:
        self.policy = policy
        self.tenant_column = tenant_column
        # strict=True denies reads of a scoped model that has no read rule, rather
        # than defaulting it to tenant-scope-only (within-tenant default deny).
        self.strict = strict
        # Secure-by-default: raises if any non-global model lacks the tenant column.
        self.scoped: list[type] = discover_scoped(base, policy, tenant_column)
        self._session_class = session_class
        self._read: Callable[[ORMExecuteState], None] | None = None
        self._write: Callable[[Session, Any, Any], None] | None = None

    def install(self) -> Purview:
        """Wire the read/write guards onto the session class (idempotent)."""
        if self._read is not None:
            return self
        self._read = make_read_guard(self.policy, self.scoped, self.tenant_column, self.strict)
        self._write = make_write_guard(self.policy, self.scoped, self.tenant_column)
        event.listen(self._session_class, "do_orm_execute", self._read)
        event.listen(self._session_class, "before_flush", self._write)
        return self

    def uninstall(self) -> None:
        """Remove the guards from the session class."""
        if self._read is None or self._write is None:
            return
        event.remove(self._session_class, "do_orm_execute", self._read)
        event.remove(self._session_class, "before_flush", self._write)
        self._read = None
        self._write = None

    def bind(self, session: _SessionLike, ctx: Context[Any, Any]) -> None:
        """Bind ``ctx`` to ``session`` so reads filter and writes are guarded."""
        bind_context(session, ctx)

    def context(self, session: _SessionLike) -> Context[Any, Any]:
        """The context bound to ``session`` (raises if the session is unbound)."""
        return self._ctx(session)

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
        """Whether ``resource`` may be created in the bound actor's tenant."""
        return _validate_create(self._ctx(session), resource, self.tenant_column)

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
    session_class: type[Session] = Session,
) -> Purview:
    """Discover scoped models, wire the guards, and return the enforcer.

    Set ``strict=True`` to deny reads of a scoped model that has no read rule
    (within-tenant default deny) instead of defaulting it to tenant-scope-only.

    Raises :class:`~purview.exceptions.UnscopedModel` if a non-global model lacks
    the tenant column.
    """
    return Purview(
        policy,
        base,
        tenant_column=tenant_column,
        strict=strict,
        session_class=session_class,
    ).install()
