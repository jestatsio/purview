"""The FastAPI edge: resolve a Context, bind it to the request session, guard
routes, and surface denials as HTTP 403.

Requires the optional dependency (``pip install purview[fastapi]``).
"""

from __future__ import annotations

from purview.fastapi.dependencies import context_binder
from purview.fastapi.errors import install_error_handlers
from purview.fastapi.guards import authorize_or_403, requires

__all__ = [
    "authorize_or_403",
    "context_binder",
    "install_error_handlers",
    "requires",
]
