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
    """A query's ambient tenant disagrees with the session's bound tenant.

    Signals a programming error (a session used for the wrong tenant), caught
    defensively before any rows are returned.
    """


class UnscopedModel(PurviewError):
    """A non-global model lacks a resolvable tenant column.

    Raised at ``install()`` time (fail closed) so a model that would otherwise
    ship unscoped is rejected at startup rather than leaking at query time.
    """
