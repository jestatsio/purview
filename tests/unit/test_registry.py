from __future__ import annotations

from typing import Any

from purview import READ, UPDATE, Policy


class Post:  # plain classes suffice: the registry only uses types as keys
    pass


class Comment:
    pass


def _noop(ctx: Any) -> list[Any]:
    return []


def test_rule_registration_and_lookup() -> None:
    policy = Policy()
    decorated = policy.rule(Post, READ)(_noop)
    assert decorated is _noop  # decorator returns the function unchanged
    assert policy.has_rules(Post, READ)
    assert policy.rules_for(Post, READ) == [_noop]
    assert not policy.has_rules(Post, UPDATE)
    assert policy.rules_for(Comment, READ) == []


def test_multiple_rules_same_key_preserved_in_order() -> None:
    policy = Policy()

    def r1(ctx: Any) -> list[Any]:
        return []

    def r2(ctx: Any) -> list[Any]:
        return []

    policy.rule(Post, READ)(r1)
    policy.rule(Post, READ)(r2)
    assert policy.rules_for(Post, READ) == [r1, r2]


def test_global_model_marker_works_as_decorator() -> None:
    policy = Policy()
    assert not policy.is_global(Post)
    returned = policy.global_model(Post)
    assert returned is Post
    assert policy.is_global(Post)
    assert Post in policy.global_models


def test_tenant_field_override() -> None:
    policy = Policy()
    assert policy.tenant_field_for(Post, "tenant_id") == "tenant_id"
    policy.set_tenant_field(Post, "org_id")
    assert policy.tenant_field_for(Post, "tenant_id") == "org_id"


def test_rules_for_returns_a_copy() -> None:
    policy = Policy()
    policy.rule(Post, READ)(_noop)
    leaked = policy.rules_for(Post, READ)
    leaked.append(_noop)
    assert policy.rules_for(Post, READ) == [_noop]  # internal list untouched
