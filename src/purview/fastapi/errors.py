"""Translate :class:`~purview.exceptions.PurviewForbidden` into HTTP 403."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from purview.exceptions import CrossTenantWrite, PurviewForbidden


def install_error_handlers(app: FastAPI) -> None:
    """Register 403 handlers for :class:`PurviewForbidden` and :class:`CrossTenantWrite`.

    Both represent an actor attempting something they are not permitted to do —
    a denied read/action, or a write into another tenant.
    """

    async def forbidden_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc) or "forbidden"})

    app.add_exception_handler(PurviewForbidden, forbidden_handler)
    app.add_exception_handler(CrossTenantWrite, forbidden_handler)
