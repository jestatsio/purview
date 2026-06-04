"""Binding an actor context to a session.

Tenancy is the session boundary: a session carries exactly one actor's
:class:`~purview.core.context.Context` in ``session.info``. Both the async
session and its underlying sync session share the same ``info`` dict, so the
guards (which run on the sync session) read what the caller bound on either.
"""

from __future__ import annotations

from typing import Any, Protocol

from purview.core.context import Context

CONTEXT_KEY = "purview_context"


class _HasInfo(Protocol):
    @property
    def info(self) -> dict[Any, Any]: ...


def bind_context(session: _HasInfo, ctx: Context[Any, Any]) -> None:
    """Bind ``ctx`` to ``session`` so the guards enforce on its behalf."""
    session.info[CONTEXT_KEY] = ctx


def context_of(session: _HasInfo) -> Context[Any, Any] | None:
    """The context bound to ``session``, or ``None`` if it is unbound."""
    value = session.info.get(CONTEXT_KEY)
    if isinstance(value, Context):
        return value
    return None
