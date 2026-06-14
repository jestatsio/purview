"""Predicate helpers compile to the expected SQL and preserve default-deny."""

from __future__ import annotations

from sqlalchemy import ColumnElement, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from purview import Context, in_values, owned_by


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column()
    section_id: Mapped[int] = mapped_column()


def _sql(expr: ColumnElement[bool]) -> str:
    return str(expr.compile(compile_kwargs={"literal_binds": True}))


def _ctx(user_id: int = 7) -> Context[int, int]:
    return Context(user_id=user_id, tenant_id=1)


def test_owned_by_compiles_to_equality() -> None:
    assert _sql(owned_by(Post.author_id, _ctx(7))) == _sql(Post.author_id == 7)


def test_in_values_compiles_to_in() -> None:
    assert _sql(in_values(Post.section_id, [1, 2, 3])) == _sql(Post.section_id.in_([1, 2, 3]))


def test_in_values_empty_is_default_deny() -> None:
    assert _sql(in_values(Post.section_id, [])) == _sql(false())


def test_in_values_accepts_any_iterable() -> None:
    assert _sql(in_values(Post.section_id, (i for i in (5, 6)))) == _sql(
        Post.section_id.in_([5, 6])
    )


def test_predicates_shim_re_exports() -> None:
    from purview import predicates

    assert predicates.owned_by is owned_by
    assert predicates.in_values is in_values
