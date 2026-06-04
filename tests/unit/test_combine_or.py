"""Granting predicates are OR-combined across a rule's return value and across
multiple rules for the same key."""

from __future__ import annotations

from collections.abc import Iterable

from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import ColumnElement, false, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from purview import READ, Context, Policy
from purview.core.combine import evaluate_predicate


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column()
    author_id: Mapped[int] = mapped_column()


def _sql(expr: ColumnElement[bool]) -> str:
    return str(expr.compile(compile_kwargs={"literal_binds": True}))


def _ctx(roles: Iterable[str] = ()) -> Context[int, int]:
    return Context(user_id=1, tenant_id=1, roles=frozenset(roles))


def test_single_predicate_returned_unwrapped() -> None:
    policy = Policy()

    @policy.rule(Post, READ)
    def _r(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return [Post.author_id == ctx.user_id]

    result = evaluate_predicate(policy, _ctx(), Post, READ)
    assert _sql(result) == _sql(Post.author_id == 1)


def test_two_predicates_from_one_rule_or_combined() -> None:
    policy = Policy()

    @policy.rule(Post, READ)
    def _r(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return [Post.author_id == ctx.user_id, Post.org_id == ctx.tenant_id]

    result = evaluate_predicate(policy, _ctx(), Post, READ)
    assert _sql(result) == _sql(or_(Post.author_id == 1, Post.org_id == 1))


def test_predicates_across_multiple_rules_or_combined() -> None:
    policy = Policy()

    @policy.rule(Post, READ)
    def _r1(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return [Post.author_id == ctx.user_id]

    @policy.rule(Post, READ)
    def _r2(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return [Post.org_id == ctx.tenant_id]

    result = evaluate_predicate(policy, _ctx(), Post, READ)
    assert _sql(result) == _sql(or_(Post.author_id == 1, Post.org_id == 1))


@given(roles=st.sets(st.sampled_from(["author", "admin", "guest"])))
def test_default_deny_invariant_over_role_combinations(roles: set[str]) -> None:
    policy = Policy()

    @policy.rule(Post, READ)
    def _r(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []

    result = evaluate_predicate(policy, _ctx(roles), Post, READ)
    assert (_sql(result) == _sql(false())) == ("author" not in roles)
