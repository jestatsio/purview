"""Route and object guards.

``requires`` is a coarse route-level gate — it 403s an actor who could never
perform the action (no standing grant), without touching a row.
``authorize_or_403`` is the object-level check: the same EXISTS check as
``Purview.authorize``, raising :class:`~purview.exceptions.PurviewForbidden` (→ 403)
when denied.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from purview.core.context import Context
from purview.exceptions import PurviewForbidden
from purview.sqlalchemy.enforcer import Purview
from purview.sqlalchemy.predicates import grants

R = TypeVar("R")


def requires(
    pv: Purview,
    action: str,
    resource_type: type,
    context_dependency: Callable[..., Any],
) -> Callable[..., Awaitable[None]]:
    """A route dependency that 403s an actor with no standing grant for the action.

    Collection routes still filter per-row afterwards; this only short-circuits
    actors who categorically cannot perform ``action`` on ``resource_type``.
    """

    async def guard(context: Context[Any, Any] = Depends(context_dependency)) -> None:
        if not grants(pv.policy, context, resource_type, action, pv.strict):
            raise PurviewForbidden(f"not permitted to {action} {resource_type.__name__}")

    return guard


async def authorize_or_403(
    pv: Purview,
    session: AsyncSession,
    action: str,
    resource: R,
) -> R:
    """Return ``resource`` if the bound actor may ``action`` it, else 403."""
    if not await pv.authorize(session, action, resource):
        raise PurviewForbidden(f"not permitted to {action} {type(resource).__name__}")
    return resource
