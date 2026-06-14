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

import warnings
from collections.abc import Callable, Sequence

from sqlalchemy.orm import ORMExecuteState, with_loader_criteria

from purview.core.actions import READ
from purview.core.registry import Policy
from purview.exceptions import PurviewWarning
from purview.sqlalchemy.binding import context_of
from purview.sqlalchemy.bypass import is_bypassed
from purview.sqlalchemy.predicates import row_predicate, tenant_predicate


def make_read_guard(
    policy: Policy,
    scoped: Sequence[type],
    tenant_column: str,
    strict: bool = False,
    warn: bool = False,
) -> Callable[[ORMExecuteState], None]:
    """Build a ``do_orm_execute`` handler enforcing tenant + read criteria.

    When ``warn`` is set, the guard additionally emits :class:`PurviewWarning` for
    the documented "sharp edges": a query on an unbound session (no tenant filter)
    and a raw/non-ORM statement on a bound session (which the guard cannot shape).
    Warnings are advisory only and never change what is enforced.
    """

    def read_guard(state: ORMExecuteState) -> None:
        if is_bypassed():
            return
        ctx = context_of(state.session)
        if ctx is None:
            if warn and state.is_select:
                warnings.warn(
                    "query executed on a session with no bound Purview context; "
                    "no tenant filtering is applied. "
                    f"statement: {str(state.statement)[:200]}",
                    PurviewWarning,
                    stacklevel=2,
                )
            return
        if warn and not getattr(state, "is_orm_statement", True):
            warnings.warn(
                "raw/non-ORM statement executed on a Purview-bound session; it is "
                "NOT tenant-filtered (Purview shapes ORM statements only). "
                f"statement: {str(state.statement)[:200]}",
                PurviewWarning,
                stacklevel=2,
            )
        if not state.is_select:
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
