"""The SQLAlchemy enforcement engine: session hooks, the EXISTS check, tenant
binding, and the bypass escape hatch.

Typical wiring::

    from purview import Policy
    from purview.sqlalchemy import install

    policy = Policy()
    pv = install(Base, policy, tenant_column="org_id")

    async with async_session() as s:
        pv.bind(s, ctx)
        posts = await s.scalars(select(Post))      # auto-filtered
        allowed = await pv.authorize(s, "update", post)
"""

from __future__ import annotations

from purview.sqlalchemy.binding import bind_context, context_of
from purview.sqlalchemy.bypass import bypass, is_bypassed
from purview.sqlalchemy.enforcer import Purview, install
from purview.sqlalchemy.filtering import authorized_select

__all__ = [
    "Purview",
    "authorized_select",
    "bind_context",
    "bypass",
    "context_of",
    "install",
    "is_bypassed",
]
