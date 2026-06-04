"""The tracker's authorization policy — one definition per rule.

* ``LegacyImport`` is scoped by its own ``account_id`` column.
* ``Task`` reads are role-shaped: members see the tasks assigned to them; admins
  see every task in the workspace.
* A ``Project`` may only be created with the creator as owner.
* ``Membership``, ``Project``, ``LegacyImport`` have no read rule, so any member
  of the workspace sees them (tenant scope still applies).
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, true

from purview import READ, Context, Policy

from .models import LegacyImport, Project, Task, User, Workspace


def build_policy() -> Policy:
    policy = Policy()
    policy.global_model(Workspace)
    policy.global_model(User)
    policy.set_tenant_field(LegacyImport, "account_id")  # per-model tenant column

    @policy.rule(Task, READ)
    def read_task(ctx: Context) -> list[ColumnElement[bool]]:
        rules: list[ColumnElement[bool]] = []
        if ctx.has_role("member"):
            rules.append(Task.assignee_id == ctx.user_id)
        if ctx.has_role("admin"):
            rules.append(true())
        return rules

    @policy.create_rule(Project)
    def project_owner_is_creator(ctx: Context, project: Project) -> bool:
        return project.owner_id == ctx.user_id

    return policy
