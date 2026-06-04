"""Create validation.

``create`` is handled separately from filtering because there is no existing row
to filter against: it validates the proposed tenant instead. The structural
guarantee — that a row cannot be persisted into another tenant — is enforced by
the write guard at flush time; this is the pre-flush check the route layer can
call to fail fast with a 403 rather than at commit.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from purview.core.context import Context

if TYPE_CHECKING:
    from purview.core.types import CreateRuleFn


def validate_create(
    ctx: Context[Any, Any],
    resource: object,
    tenant_column: str,
    create_rules: Iterable[CreateRuleFn] = (),
) -> bool:
    """Whether ``resource`` may be created in ``ctx``'s tenant.

    The proposed tenant must be unset (the write guard will stamp it) or match the
    session's tenant, and every registered create rule must pass.
    """
    proposed = getattr(resource, tenant_column, None)
    if proposed is not None and proposed != ctx.tenant_id:
        return False
    return all(rule(ctx, resource) for rule in create_rules)
