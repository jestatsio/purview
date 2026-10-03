"""The check form.

The same predicate used to filter a collection is, for a single object, wrapped
in ``EXISTS (SELECT 1 FROM t WHERE pk = :id AND <tenant> AND <predicate>)`` and
evaluated by the database — so relationship/join predicates are handled correctly
without re-implementing SQL semantics in Python.

``batch_check`` answers the same question for many ids in one query, avoiding an
N+1 of per-object EXISTS checks.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import inspect, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from purview.core.context import Context
from purview.core.registry import Policy
from purview.sqlalchemy.bypass import _CHECK_EXECUTION_OPTION
from purview.sqlalchemy.predicates import row_predicate, scope_predicate


def _primary_key_columns(model: type) -> Sequence[Any]:
    return inspect(model).primary_key


async def exists_check(
    session: AsyncSession,
    policy: Policy,
    ctx: Context[Any, Any],
    action: str,
    resource: object,
    tenant_column: str,
    strict: bool = False,
) -> bool:
    """Whether ``ctx`` may perform ``action`` on the single ``resource`` row."""
    model = type(resource)
    mapper: Any = inspect(model)
    pk_match = [
        col == getattr(resource, mapper.get_property_by_column(col).key)
        for col in _primary_key_columns(model)
    ]
    inner = (
        select(literal(1))
        .select_from(model)
        .where(
            *pk_match,
            scope_predicate(policy, ctx, model, tenant_column),
            row_predicate(policy, ctx, model, action, strict),
        )
    )
    # Skip only this query's redundant read criteria. Autoflush and any reads
    # issued by flush hooks retain their normal enforcement.
    stmt = select(inner.exists()).execution_options(**{_CHECK_EXECUTION_OPTION: True})
    return bool(await session.scalar(stmt))


async def batch_check(
    session: AsyncSession,
    policy: Policy,
    ctx: Context[Any, Any],
    action: str,
    model: type,
    ids: Iterable[Any],
    tenant_column: str,
    strict: bool = False,
) -> list[Any]:
    """The subset of ``ids`` of ``model`` that ``ctx`` may perform ``action`` on.

    For a single-column primary key, ``ids`` and the result are scalar values; for a
    composite key, they are tuples of the key columns in primary-key order.
    """
    tenant = scope_predicate(policy, ctx, model, tenant_column)
    row = row_predicate(policy, ctx, model, action, strict)
    pk_cols = list(_primary_key_columns(model))

    if len(pk_cols) == 1:
        pk = pk_cols[0]
        stmt = (
            select(pk)
            .select_from(model)
            .where(pk.in_(list(ids)), tenant, row)
            .execution_options(**{_CHECK_EXECUTION_OPTION: True})
        )
        return list(await session.scalars(stmt))

    keys = [tuple(i) for i in ids]
    composite = (
        select(*pk_cols)
        .select_from(model)
        .where(tuple_(*pk_cols).in_(keys), tenant, row)
        .execution_options(**{_CHECK_EXECUTION_OPTION: True})
    )
    rows = (await session.execute(composite)).all()
    result: list[Any] = [tuple(r) for r in rows]
    return result
