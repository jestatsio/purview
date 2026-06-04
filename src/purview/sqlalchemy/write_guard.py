"""The write guard.

Two handlers close the write path and keep one tenant per session:

* ``before_attach`` refuses an object carrying another tenant's id from being
  added or merged into a session bound to this tenant — so the identity map only
  ever holds this tenant's rows (closes the cross-session re-attach / merge hole).
* ``before_flush`` auto-populates the tenant on inserts with none set, rejects
  forged-tenant inserts, and rejects updates that move a row across the boundary.

These guard writes only; reads are guarded separately by the read guard.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy.orm import Session

from purview.core.registry import Policy
from purview.exceptions import CrossTenantWrite
from purview.sqlalchemy.binding import context_of
from purview.sqlalchemy.bypass import is_bypassed


def make_write_guard(
    policy: Policy,
    scoped: Sequence[type],
    tenant_column: str,
) -> Callable[[Session, Any, Any], None]:
    """Build a ``before_flush`` handler enforcing tenant ownership of writes."""

    def _column_for(obj: object) -> str | None:
        if policy.is_global(type(obj)):
            return None
        column = policy.tenant_field_for(type(obj), tenant_column)
        return column if hasattr(obj, column) else None

    def write_guard(session: Session, flush_context: Any, instances: Any) -> None:
        if is_bypassed():
            return
        ctx = context_of(session)
        if ctx is None:
            return

        for obj in session.new:
            column = _column_for(obj)
            if column is None:
                continue
            current = getattr(obj, column, None)
            if current is None:
                setattr(obj, column, ctx.tenant_id)
            elif current != ctx.tenant_id:
                raise CrossTenantWrite(
                    f"refusing to insert {type(obj).__name__} into tenant "
                    f"{current!r} from a session bound to tenant {ctx.tenant_id!r}"
                )

        for obj in session.dirty:
            column = _column_for(obj)
            if column is None or not session.is_modified(obj, include_collections=False):
                continue
            current = getattr(obj, column, None)
            if current != ctx.tenant_id:
                raise CrossTenantWrite(
                    f"refusing to move {type(obj).__name__} to tenant {current!r} "
                    f"from a session bound to tenant {ctx.tenant_id!r}"
                )

    return write_guard


def make_attach_guard(
    policy: Policy,
    tenant_column: str,
) -> Callable[[Session, object], None]:
    """Build a ``before_attach`` handler that refuses a foreign-tenant object.

    A transient object with no tenant set is allowed (the write guard stamps it on
    flush); an object already carrying a *different* tenant's id cannot enter the
    session, whether via ``add`` or ``merge``.
    """

    def attach_guard(session: Session, instance: object) -> None:
        if is_bypassed():
            return
        ctx = context_of(session)
        if ctx is None or policy.is_global(type(instance)):
            return
        column = policy.tenant_field_for(type(instance), tenant_column)
        if not hasattr(instance, column):
            return
        current = getattr(instance, column, None)
        if current is not None and current != ctx.tenant_id:
            raise CrossTenantWrite(
                f"refusing to attach {type(instance).__name__} bound to tenant "
                f"{current!r} to a session bound to tenant {ctx.tenant_id!r}"
            )

    return attach_guard
