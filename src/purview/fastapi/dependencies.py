"""Context resolution for FastAPI.

Purview consumes an already-authenticated identity; the host app supplies two
dependencies — one that yields the request's :class:`AsyncSession`, one that
resolves the actor's :class:`~purview.core.context.Context` (one async hit to load
its tenant-scoped roles). ``context_binder`` ties them together into a single
dependency that binds the context to the session, so reads filter automatically.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from purview.core.context import Context
from purview.sqlalchemy.enforcer import Purview


def context_binder(
    pv: Purview,
    session_dependency: Callable[..., Any],
    context_dependency: Callable[..., Any],
) -> Callable[..., Awaitable[AsyncSession]]:
    """A dependency that binds the resolved context to the request session.

    Inject the result into routes to obtain a session whose reads are already
    scoped to the actor::

        bound = context_binder(pv, get_session, get_context)

        @app.get("/posts")
        async def list_posts(session: AsyncSession = Depends(bound)):
            return (await session.scalars(select(Post))).all()
    """

    async def bound_session(
        session: AsyncSession = Depends(session_dependency),
        context: Context[Any, Any] = Depends(context_dependency),
    ) -> AsyncSession:
        pv.bind(session, context)
        return session

    return bound_session
