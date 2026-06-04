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


def is_bypassed() -> bool:
    """Whether enforcement is currently suppressed on this task."""
    return _active.get()


@contextmanager
def bypass(reason: str) -> Iterator[None]:
    """Suspend all Purview enforcement within the block.

    A non-empty ``reason`` is required and logged at WARNING — bypasses are meant
    to be visible in logs and greppable in code::

        with policy.bypass(reason="nightly billing rollup"):
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


@contextmanager
def _suppress() -> Iterator[None]:
    """Internal, silent suppression used while Purview builds its own fully
    self-contained predicates (e.g. the EXISTS check), so the guards do not
    double-apply criteria to queries Purview itself issues."""
    token = _active.set(True)
    try:
        yield
    finally:
        _active.reset(token)
