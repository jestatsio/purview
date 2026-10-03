# Quickstart

Run a complete example with an in-memory SQLite database. It creates three posts,
binds an author to tenant 1, and shows that only their own post is returned.

## 1. Install

```bash
uv init purview-demo
cd purview-demo
uv add "purview-authz[sqlite]"
```

Prefer pip? Follow the [virtual environment instructions](installation.md) and use
`python quickstart.py` below.

## 2. Add the example

Save this as `quickstart.py`, or copy it from
[the repository](https://github.com/jestatsio/purview/blob/main/examples/quickstart.py).
This page includes that file directly, so the example and documentation stay in sync.

```python title="quickstart.py"
--8 < --"examples/quickstart.py"
```

## 3. Run it

```bash
uv run python quickstart.py
```

Expected output:

```text
['My draft']
None
True
```

The other author's post fails the read policy. The third post belongs to another
tenant, even though its author ID matches. Both are filtered out.

## What happened

1. **Define a model.** `Post.tenant_id` is the tenant field. All mapped models under
   `Base` must have this field unless explicitly marked global.
2. **Register a rule.** Authors contribute an ownership predicate. Other actors
   contribute no predicates, so the rule denies access.
3. **Install once.** `install()` validates the mapped models and registers SQLAlchemy
   session event handlers. Call it after importing your application's models.
4. **Bind before querying.** A fresh session receives the authenticated actor's
   `Context`. The read guard adds both tenant and row predicates.
5. **Check an object explicitly.** `authorize()` uses a database `EXISTS` query for
   the object's primary key, tenant, and action predicate.

The separate seed session is intentionally unbound. Unbound sessions have no
automatic filtering, which is useful for trusted setup work. Request handlers
should always use a fresh bound session.

## Choose your default

The example uses `strict=True`. This denies reads for scoped models that have no
read rule. In the default `strict=False` mode, a scoped model with no read rule is
visible to all actors within the bound tenant. In both modes, a registered rule
that returns no granting predicates denies access.

## Add write permissions

`authorize(session, "update", post)` checks update permission. When there is no
update rule, Purview falls back to the read rule. Define an update rule when editing
should be more restrictive than reading, then check **before changing the object**:

```python
from purview import PurviewForbidden

if not await pv.authorize(session, "update", post):
    raise PurviewForbidden("You cannot edit this post")
post.title = "Revised draft"
await session.commit()
```

The tenant flush guard does not automatically call your update, delete, or create
rules. Use explicit helpers for those permissions. See
[writing policies](policies.md) for create validation and
[FastAPI integration](fastapi.md) for complete request-handler patterns.
