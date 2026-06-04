from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from purview import Context


def test_defaults_to_empty_roles() -> None:
    ctx = Context(user_id=1, tenant_id=2)
    assert ctx.roles == frozenset()
    assert ctx.user_id == 1
    assert ctx.tenant_id == 2


def test_has_role_and_has_any() -> None:
    ctx = Context(user_id=1, tenant_id=1, roles=frozenset({"author", "editor"}))
    assert ctx.has_role("author")
    assert not ctx.has_role("admin")
    assert ctx.has_any("admin", "editor")
    assert not ctx.has_any("admin", "guest")


def test_roles_coerced_from_arbitrary_iterable() -> None:
    ctx = Context(user_id=1, tenant_id=1, roles=["a", "a", "b"])  # type: ignore[arg-type]
    assert ctx.roles == frozenset({"a", "b"})
    assert isinstance(ctx.roles, frozenset)


def test_is_frozen() -> None:
    ctx = Context(user_id=1, tenant_id=1)
    with pytest.raises(FrozenInstanceError):
        ctx.user_id = 2  # type: ignore[misc]


def test_equality_and_hashable() -> None:
    a = Context(1, 1, frozenset({"x"}))
    b = Context(1, 1, frozenset({"x"}))
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
