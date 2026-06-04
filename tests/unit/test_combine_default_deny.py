"""Default-deny is the security spine: no granting predicate must compile to
``false()``. These tests cover every path that yields a denial."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import ColumnElement, false
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


def test_no_rules_registered_denies() -> None:
    policy = Policy()
    result = evaluate_predicate(policy, _ctx(), Post, READ)
    assert _sql(result) == _sql(false())


def test_rule_returning_empty_list_denies() -> None:
    policy = Policy()

    @policy.rule(Post, READ)
    def _r(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return []

    result = evaluate_predicate(policy, _ctx(), Post, READ)
    assert _sql(result) == _sql(false())


def test_no_granting_role_denies_but_granting_role_does_not() -> None:
    policy = Policy()

    @policy.rule(Post, READ)
    def _r(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []

    assert _sql(evaluate_predicate(policy, _ctx(), Post, READ)) == _sql(false())
    granted = evaluate_predicate(policy, _ctx(["author"]), Post, READ)
    assert _sql(granted) != _sql(false())
