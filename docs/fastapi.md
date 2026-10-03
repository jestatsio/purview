# FastAPI integration

Purview consumes your application's authenticated identity. The adapter connects a
trusted `Context` and a request-scoped `AsyncSession` through FastAPI dependencies.

```bash
uv add "purview-authz[fastapi,postgres]" "uvicorn[standard]"
```

Use the `sqlite` extra instead of `postgres` if your app uses SQLite.

## Bind one session per request

The following wiring assumes your app already provides `Base`, `Post`, `policy`,
`sessions`, and `get_context`. The [quickstart](quickstart.md) demonstrates the model,
policy, and session setup. Implement `get_context` using your authentication system.

```python
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from purview import READ, PurviewForbidden
from purview.fastapi import authorize_or_403, context_binder, install_error_handlers
from purview.sqlalchemy import install

pv = install(Base, policy, strict=True)
app = FastAPI()
install_error_handlers(app)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessions() as session:
        yield session


bound = context_binder(pv, get_session, get_context)
```

`get_context` must verify the principal's identity and membership in the selected
tenant, then return their roles for that tenant. Do not trust a caller-supplied user
ID, tenant ID, or role as authorization evidence. Any database work needed to resolve
identity should use a separate session with explicit application-owned constraints.

Use `Depends(bound)` in handlers so application data is loaded only after binding.
Purview does not issue authentication tokens or provide a login system.

## List and retrieve

```python
@app.get("/posts")
async def list_posts(session: AsyncSession = Depends(bound)):
    posts = (await session.scalars(select(Post))).all()
    return [{"id": post.id, "title": post.title} for post in posts]


@app.get("/posts/{post_id}")
async def get_post(post_id: int, session: AsyncSession = Depends(bound)):
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"id": post.id, "title": post.title}
```

An invisible row returns the same 404 as a missing row. A collection with no visible
rows returns an empty list. With asynchronous relationships, prefer
`selectinload(...)` or SQLAlchemy's `AsyncAttrs.awaitable_attrs`.

## Update after checking

```python
class PostInput(BaseModel):
    title: str


@app.patch("/posts/{post_id}")
async def update_post(
    post_id: int,
    payload: PostInput,
    session: AsyncSession = Depends(bound),
):
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    await authorize_or_403(pv, session, "update", post)
    post.title = payload.title
    await session.commit()
    return {"id": post.id, "title": post.title}
```

Define an `update` rule when editing needs different permissions than reading.
Otherwise the explicit update check falls back to the read rule. Use
`expire_on_commit=False` on the async session factory for the return-after-commit
pattern shown here.

For deletion, check `"delete"`, then call `await session.delete(post)` and commit.
Neither `commit()` nor deleting the object automatically evaluates action rules.

## Create after validating

Register a [create rule](policies.md#validate-proposed-objects), then validate the
proposed object before adding it:

```python
@app.post("/posts", status_code=201)
async def create_post(payload: PostInput, session: AsyncSession = Depends(bound)):
    ctx = pv.context(session)
    post = Post(author_id=ctx.user_id, title=payload.title)
    if not pv.validate_create(session, post):
        raise PurviewForbidden("You cannot create this post")
    session.add(post)
    await session.commit()
    return {"id": post.id, "title": post.title}
```

The tenant ID comes from the bound context at flush. The request payload only
contains fields the caller is allowed to supply.

## Optional route gate

```python
from purview.fastapi import requires


@app.get(
    "/guarded-posts",
    dependencies=[Depends(requires(pv, READ, Post, get_context))],
)
async def guarded_posts(session: AsyncSession = Depends(bound)):
    posts = (await session.scalars(select(Post))).all()
    return [{"id": post.id, "title": post.title} for post in posts]
```

`requires()` rejects a statically denied predicate before fetching any rows. It is
a coarse gate, not a database existence check. A predicate can pass this gate and
still match zero rows. Collection filtering and object authorization remain necessary.
Use `validate_create()` for create permissions because create rules are a separate API.

## HTTP error behavior

`install_error_handlers(app)` maps `PurviewForbidden` and `CrossTenantWrite` to
HTTP 403. It does not convert a missing object into a 404 for you, so keep the
explicit `post is None` check. Errors include exception details. Register your own
handlers if your public API needs generic messages.

For a complete application, see the
[tracker example](https://github.com/jestatsio/purview/tree/main/examples/tracker).
The [HTTP integration tests](https://github.com/jestatsio/purview/blob/main/tests/examples/test_blog_app.py)
also demonstrate the adapter. Their header-based identity mechanism is a test
fixture, not production authentication.
