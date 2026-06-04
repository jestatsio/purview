"""The actor context.

Security-relevant inputs are threaded explicitly as a frozen :class:`Context`
rather than pulled from ambient state, so they stay visible at the call site and
tests stay honest. The context is resolved once per request (one async hit to
load the actor's tenant-scoped roles) and then passed to rules synchronously.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

U = TypeVar("U")
T = TypeVar("T")


@dataclass(frozen=True)
class Context(Generic[U, T]):
    """An authenticated actor, scoped to one tenant.

    Parameters
    ----------
    user_id:
        Identifier of the acting principal. Flows into predicates as a bind
        value (e.g. ``Post.author_id == ctx.user_id``).
    tenant_id:
        The single tenant this context is scoped to.
    roles:
        The actor's roles *within this tenant*. Any iterable of strings is
        accepted and normalised to a ``frozenset``.
    """

    user_id: U
    tenant_id: T
    roles: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.roles, frozenset):
            object.__setattr__(self, "roles", frozenset(self.roles))

    def has_role(self, name: str) -> bool:
        """True if the actor holds ``name`` in this tenant."""
        return name in self.roles

    def has_any(self, *names: str) -> bool:
        """True if the actor holds at least one of ``names``."""
        return any(name in self.roles for name in names)
