"""Actions.

Actions are user-defined strings; these four are the conventional set. ``READ``
holds special status: it is the action that drives query *filtering* (shaping a
collection to the rows an actor may see). All other actions are evaluated at the
instance level as yes/no checks.
"""

from __future__ import annotations

from typing import Final, TypeAlias

Action: TypeAlias = str

READ: Final[str] = "read"
CREATE: Final[str] = "create"
UPDATE: Final[str] = "update"
DELETE: Final[str] = "delete"
