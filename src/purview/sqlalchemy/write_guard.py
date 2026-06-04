"""The write guard.

A ``before_flush`` handler that closes the write path:

* **inserts** with no tenant set are auto-populated with the session's tenant;
* **inserts** that name a different tenant are rejected (forged insert);
* **updates** that move a row across the tenant boundary are rejected.

This guards writes only; reads are guarded separately by the read guard.
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

    def _is_scoped(obj: object) -> bool:
        return hasattr(obj, tenant_column) and not policy.is_global(type(obj))

    def write_guard(session: Session, flush_context: Any, instances: Any) -> None:
        if is_bypassed():
            return
        ctx = context_of(session)
        if ctx is None:
            return

        for obj in session.new:
            if not _is_scoped(obj):
                continue
            current = getattr(obj, tenant_column, None)
            if current is None:
                setattr(obj, tenant_column, ctx.tenant_id)
            elif current != ctx.tenant_id:
                raise CrossTenantWrite(
                    f"refusing to insert {type(obj).__name__} into tenant "
                    f"{current!r} from a session bound to tenant {ctx.tenant_id!r}"
                )

        for obj in session.dirty:
            if not _is_scoped(obj) or not session.is_modified(obj, include_collections=False):
                continue
            current = getattr(obj, tenant_column, None)
            if current != ctx.tenant_id:
                raise CrossTenantWrite(
                    f"refusing to move {type(obj).__name__} to tenant {current!r} "
                    f"from a session bound to tenant {ctx.tenant_id!r}"
                )

    return write_guard
