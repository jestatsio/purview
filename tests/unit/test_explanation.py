"""build_explanation compiles the tenant + row predicate the guard would apply."""

from __future__ import annotations

from sqlalchemy import ColumnElement
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from purview import READ, Context, Policy
from purview.sqlalchemy.explanation import build_explanation


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column()
    author_id: Mapped[int] = mapped_column()


class Org(Base):
    __tablename__ = "org"
    id: Mapped[int] = mapped_column(primary_key=True)


def _policy() -> Policy:
    policy = Policy()
    policy.global_model(Org)

    @policy.rule(Post, READ)
    def read_post(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
        return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []

    return policy


def _ctx(*roles: str) -> Context[int, int]:
    return Context(user_id=5, tenant_id=1, roles=frozenset(roles))


def test_granted_predicate_and_tenant_scope() -> None:
    exp = build_explanation(_policy(), _ctx("author"), Post, READ, "org_id")
    assert exp.tenant_scoped is True
    assert exp.tenant_column == "org_id"
    assert "org_id" in (exp.tenant_sql or "")
    assert "author_id = 5" in exp.row_sql
    assert exp.is_default_deny is False
    assert exp.active_roles == frozenset({"author"})


def test_default_deny_when_no_granting_role() -> None:
    exp = build_explanation(_policy(), _ctx(), Post, READ, "org_id")
    assert exp.is_default_deny is True
    assert exp.row_sql == "false"


def test_global_model_has_no_tenant_scope() -> None:
    exp = build_explanation(_policy(), _ctx(), Org, READ, "org_id")
    assert exp.tenant_scoped is False
    assert exp.tenant_sql is None
    assert exp.combined_sql == exp.row_sql


def test_update_falls_back_to_read_governing_action() -> None:
    exp = build_explanation(_policy(), _ctx("author"), Post, "update", "org_id")
    assert exp.action == "update"
    assert exp.governing_action == "read"


def test_str_renders_all_branches() -> None:
    # granted, ruled, tenant-scoped, with a contributing rule
    granted = str(build_explanation(_policy(), _ctx("author"), Post, READ, "org_id"))
    assert "tenant scope" in granted and "author_id = 5" in granted and "rules:" in granted

    # default deny + a rule that contributed nothing
    denied = str(build_explanation(_policy(), _ctx(), Post, READ, "org_id"))
    assert "default deny" in denied and "contributed nothing" in denied

    # global model branch + governing-action fallback branch
    glob = str(build_explanation(_policy(), _ctx(), Org, READ, "org_id"))
    assert "global model" in glob
    fallback = str(build_explanation(_policy(), _ctx("author"), Post, "update", "org_id"))
    assert "falls back to it" in fallback


def test_str_handles_no_active_roles() -> None:
    assert "(none)" in str(build_explanation(_policy(), _ctx(), Post, READ, "org_id"))


def test_per_rule_contributions() -> None:
    granted = build_explanation(_policy(), _ctx("author"), Post, READ, "org_id")
    assert len(granted.contributions) == 1
    (contribution,) = granted.contributions
    assert contribution.branch_count == 1
    assert "author_id = 5" in (contribution.predicate_sql or "")

    # A rule that returns nothing for this context contributes nothing.
    silent = build_explanation(_policy(), _ctx(), Post, READ, "org_id")
    assert silent.contributions[0].predicate_sql is None
    assert silent.contributions[0].branch_count == 0
