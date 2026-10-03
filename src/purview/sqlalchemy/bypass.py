"""The escape hatch.

A single, loud, greppable bypass for admin tooling and migrations. While active
on the current task, both the read guard and the write guard stand down.

``bypass`` is implemented with a :class:`contextvars.ContextVar`, so it scopes to
the current (async) task and never bleeds across requests.
"""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Iterator
from contextlib import contextmanager

_log = logging.getLogger("purview.bypass")

_active: contextvars.ContextVar[bool] = contextvars.ContextVar("purview_bypass", default=False)
# Only Purview's self-contained check statement skips redundant read criteria.
# Context-wide suppression would also bypass nested reads during autoflush.
_CHECK_EXECUTION_OPTION = "_purview_self_contained_check"


def is_bypassed() -> bool:
    """Whether enforcement is currently suppressed on this task."""
    return _active.get()


@contextmanager
def bypass(reason: str) -> Iterator[None]:
    """Suspend all Purview enforcement within the block.

    A non-empty ``reason`` is required and logged at WARNING — bypasses are meant
    to be visible in logs and greppable in code::

        with bypass(reason="nightly billing rollup"):
            ...
    """
    if not reason or not reason.strip():
        raise ValueError("bypass(reason=...) requires a non-empty reason")
    _log.warning("purview enforcement bypassed: %s", reason)
    token = _active.set(True)
    try:
        yield
    finally:
        _active.reset(token)
