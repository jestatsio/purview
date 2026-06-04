"""Binding an actor context to a session.

Tenancy is the session boundary: a session carries exactly one actor's
:class:`~purview.core.context.Context` in ``session.info``. Both the async
session and its underlying sync session share the same ``info`` dict, so the
guards (which run on the sync session) read what the caller bound on either.
"""

from __future__ import annotations

from typing import Any, Protocol

from purview.core.context import Context
from purview.exceptions import TenantMismatch

CONTEXT_KEY = "purview_context"


class _HasInfo(Protocol):
    @property
    def info(self) -> dict[Any, Any]: ...


def bind_context(session: _HasInfo, ctx: Context[Any, Any]) -> None:
    """Bind ``ctx`` to ``session`` so the guards enforce on its behalf.

    A session is bound to exactly one tenant. Rebinding it to a *different*
    tenant raises :class:`~purview.exceptions.TenantMismatch` — that would be a
    request reusing another tenant's session, exactly the cross-tenant footgun
    the session boundary exists to prevent. Rebinding within the same tenant
    (e.g. a different user) is allowed.
    """
    existing = session.info.get(CONTEXT_KEY)
    if isinstance(existing, Context) and existing.tenant_id != ctx.tenant_id:
        raise TenantMismatch(
            f"session is already bound to tenant {existing.tenant_id!r}; refusing "
            f"to rebind it to tenant {ctx.tenant_id!r}"
        )
    session.info[CONTEXT_KEY] = ctx


def context_of(session: _HasInfo) -> Context[Any, Any] | None:
    """The context bound to ``session``, or ``None`` if it is unbound."""
    value = session.info.get(CONTEXT_KEY)
    if isinstance(value, Context):
        return value
    return None
