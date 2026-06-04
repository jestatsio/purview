"""Create validation.

``create`` is handled separately from filtering because there is no existing row
to filter against: it validates the proposed tenant instead. The structural
guarantee — that a row cannot be persisted into another tenant — is enforced by
the write guard at flush time; this is the pre-flush check the route layer can
call to fail fast with a 403 rather than at commit.
"""

from __future__ import annotations

from typing import Any

from purview.core.context import Context


def validate_create(
    ctx: Context[Any, Any],
    resource: object,
    tenant_column: str,
) -> bool:
    """Whether ``resource`` may be created in ``ctx``'s tenant.

    True when the proposed tenant is unset (the write guard will stamp it) or
    already matches the session's tenant.
    """
    proposed = getattr(resource, tenant_column, None)
    return proposed is None or proposed == ctx.tenant_id
