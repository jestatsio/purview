"""build_audit classifies model read-visibility across strict and non-strict."""

from __future__ import annotations

from sqlalchemy import ColumnElement, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from purview import READ, Context, Policy
from purview.core.audit import build_audit


class Base(DeclarativeBase):
    pass


class Post(Base):  # scoped + ruled
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column()


class Comment(Base):  # scoped + no read rule
    __tablename__ = "comment"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column()


class Org(Base):  # global
    __tablename__ = "org"
    id: Mapped[int] = mapped_column(primary_key=True)


def _policy() -> Policy:
    policy = Policy()
    policy.global_model(Org)

    @policy.rule(Post, READ)
    def _r(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return [true()]

    return policy


def _by_name(report: object) -> dict[str, str]:
    return {m.model: m.visibility for m in report.models}  # type: ignore[attr-defined]


def test_classifications_non_strict() -> None:
    report = build_audit(_policy(), [Post, Comment], [Org], "org_id", strict=False)
    visibility = _by_name(report)
    assert visibility == {"Post": "ruled", "Comment": "tenant-wide", "Org": "global"}
    assert {m.model for m in report.tenant_wide_models} == {"Comment"}


def test_strict_flips_unruled_to_default_deny() -> None:
    report = build_audit(_policy(), [Post, Comment], [Org], "org_id", strict=True)
    visibility = _by_name(report)
    assert visibility["Comment"] == "default-deny"
    assert report.tenant_wide_models == ()


def test_report_str_lists_models_and_flags() -> None:
    report = build_audit(_policy(), [Post, Comment], [Org], "org_id")
    text = str(report)
    assert "Post" in text and "ruled" in text
    assert "Comment" in text and "tenant-wide" in text
    assert "no read rule" in text  # the flagged summary line


def test_report_str_without_findings_omits_flag_line() -> None:
    report = build_audit(_policy(), [Post], [Org], "org_id")  # Post is ruled
    assert "no read rule" not in str(report)


def test_tenant_column_recorded_for_scoped_models() -> None:
    report = build_audit(_policy(), [Post], [Org], "org_id")
    post = next(m for m in report.models if m.model == "Post")
    org = next(m for m in report.models if m.model == "Org")
    assert post.tenant_scoped and post.tenant_column == "org_id"
    assert not org.tenant_scoped and org.tenant_column is None
