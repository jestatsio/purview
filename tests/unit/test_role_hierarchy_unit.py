"""Role implications expand to a transitive, cycle-safe closure."""

from __future__ import annotations

from purview import Policy


def test_no_implications_returns_input_unchanged() -> None:
    policy = Policy()
    assert policy.expand_roles({"author"}) == frozenset({"author"})
    assert policy.expand_roles([]) == frozenset()


def test_direct_implication() -> None:
    policy = Policy()
    policy.role_implies("admin", "editor")
    assert policy.expand_roles({"admin"}) == frozenset({"admin", "editor"})


def test_transitive_chain() -> None:
    policy = Policy()
    policy.role_implies("admin", "editor")
    policy.role_implies("editor", "viewer")
    assert policy.expand_roles({"admin"}) == frozenset({"admin", "editor", "viewer"})


def test_multiple_implied_in_one_call() -> None:
    policy = Policy()
    policy.role_implies("admin", "editor", "viewer")
    assert policy.expand_roles({"admin"}) == frozenset({"admin", "editor", "viewer"})


def test_cycle_terminates() -> None:
    policy = Policy()
    policy.role_implies("a", "b")
    policy.role_implies("b", "a")
    assert policy.expand_roles({"a"}) == frozenset({"a", "b"})


def test_self_loop_is_harmless() -> None:
    policy = Policy()
    policy.role_implies("x", "x")
    assert policy.expand_roles({"x"}) == frozenset({"x"})


def test_unknown_roles_pass_through() -> None:
    policy = Policy()
    policy.role_implies("admin", "editor")
    assert policy.expand_roles({"guest"}) == frozenset({"guest"})


def test_closure_of_closure_is_idempotent() -> None:
    policy = Policy()
    policy.role_implies("admin", "editor")
    policy.role_implies("editor", "viewer")
    once = policy.expand_roles({"admin"})
    assert policy.expand_roles(once) == once
