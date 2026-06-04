"""Purview exception hierarchy.

All errors derive from :class:`PurviewError` so callers can catch the whole
family with one ``except``.
"""

from __future__ import annotations


class PurviewError(Exception):
    """Base class for every error raised by Purview."""


class PurviewForbidden(PurviewError):
    """An actor is not permitted to perform an action on a resource.

    The FastAPI adapter translates this into an HTTP 403 response.
    """


class CrossTenantWrite(PurviewError):
    """A flush would write a row into a tenant other than the session's.

    Raised by the write guard for forged-tenant inserts and for updates that
    move an existing row across the tenant boundary.
    """


class TenantMismatch(PurviewError):
    """A session bound to one tenant is being rebound to a different one.

    Raised by ``bind_context`` / ``Purview.bind`` when a request would reuse a
    session that already carries another tenant's context — the cross-tenant
    footgun the session boundary exists to prevent.
    """


class UnscopedModel(PurviewError):
    """A non-global model lacks a resolvable tenant column.

    Raised at ``install()`` time (fail closed) so a model that would otherwise
    ship unscoped is rejected at startup rather than leaking at query time.
    """
