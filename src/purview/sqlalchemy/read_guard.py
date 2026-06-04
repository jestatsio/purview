"""The read guard.

A ``do_orm_execute`` handler that, for every scoped entity present in a select,
applies the tenant-scope criteria and (when the model has read rules) the
fine-grained read predicate via ``with_loader_criteria``. Because
``with_loader_criteria`` propagates to relationship loads, this scopes lazy and
eager loads as well as top-level selects.

Criteria for an entity that is absent from a given statement is a harmless no-op,
so applying every scoped entity's criteria to every select is safe — and means
enforcement never relies solely on propagation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy.orm import ORMExecuteState, with_loader_criteria

from purview.core.actions import READ
from purview.core.registry import Policy
from purview.sqlalchemy.binding import context_of
from purview.sqlalchemy.bypass import is_bypassed
from purview.sqlalchemy.predicates import row_predicate, tenant_predicate


def make_read_guard(
    policy: Policy,
    scoped: Sequence[type],
    tenant_column: str,
    strict: bool = False,
) -> Callable[[ORMExecuteState], None]:
    """Build a ``do_orm_execute`` handler enforcing tenant + read criteria."""

    def read_guard(state: ORMExecuteState) -> None:
        if not state.is_select or is_bypassed():
            return
        ctx = context_of(state.session)
        if ctx is None:
            return
        for entity in scoped:
            column = policy.tenant_field_for(entity, tenant_column)
            state.statement = state.statement.options(
                with_loader_criteria(
                    entity,
                    tenant_predicate(entity, column, ctx.tenant_id),
                    include_aliases=True,
                )
            )
            # Apply the read predicate when the model is ruled, or always under
            # strict (where an unruled model must deny rather than be open).
            if policy.has_rules(entity, READ) or strict:
                state.statement = state.statement.options(
                    with_loader_criteria(
                        entity,
                        row_predicate(policy, ctx, entity, READ, strict),
                        include_aliases=True,
                    )
                )

    return read_guard
