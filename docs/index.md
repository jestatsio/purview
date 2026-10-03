---
hide:
  - navigation
  - toc
---

<div class="pv-hero" markdown>

<p class="pv-eyebrow">Python policies. SQL enforcement.</p>

# Authorization that speaks SQLAlchemy.

<p class="pv-lead">Keep tenant data scoped and row permissions close to your models. Write a policy in Python, then use it for filtered ORM reads and explicit permission checks.</p>

<div class="pv-actions" markdown>

[Start building](quickstart.md){ .md-button .md-button--primary }
[Explore the API](reference.md){ .md-button }

</div>

<p class="pv-meta">Python 3.11+ &nbsp; / &nbsp; SQLAlchemy 2 &nbsp; / &nbsp; FastAPI ready &nbsp; / &nbsp; MIT licensed</p>

</div>

<div class="pv-grid" markdown>

<div class="pv-card" markdown>

### One policy definition

SQLAlchemy predicates power both collection filtering and explicit object checks. The database evaluates your rules.

</div>

<div class="pv-card" markdown>

### A tenant per session

Bind an actor to a fresh session. Purview adds tenant criteria to ORM reads and checks tenant IDs during object writes.

</div>

<div class="pv-card" markdown>

### Fits your Python stack

Use familiar models, queries, and tools. Add FastAPI dependencies when you need them. No separate policy service.

</div>

</div>

## Start with a rule

This policy lets authors read their own posts. The session's tenant filter applies
alongside it.

```python
from purview import READ, Context, Policy
from purview.sqlalchemy import install

policy = Policy()


@policy.rule(Post, READ)
def read_posts(ctx: Context):
    return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []


pv = install(Base, policy, strict=True)
```

Bind the authenticated actor, then use an ordinary SQLAlchemy query:

```python
async with sessions() as session:
    pv.bind(session, Context(user_id=42, tenant_id=1, roles={"author"}))
    posts = (await session.scalars(select(Post))).all()
```

[Run the complete SQLite example →](quickstart.md)

<div class="pv-flow" role="img" aria-label="An authenticated actor's context is combined with tenant and policy predicates to produce filtered SQL rows">
  <div class="pv-flow-step"><strong>Actor context</strong><span>User · tenant · roles</span></div>
  <span class="pv-flow-arrow" aria-hidden="true">→</span>
  <div class="pv-flow-step"><strong>Tenant + policy</strong><span>SQLAlchemy predicates</span></div>
  <span class="pv-flow-arrow" aria-hidden="true">→</span>
  <div class="pv-flow-step"><strong>Filtered SQL</strong><span>Rows the actor may read</span></div>
</div>

## Small API. Explicit boundaries.

Reads filter automatically on bound sessions. For writes, your application calls
`authorize()` before update or delete and `validate_create()` for create rules.
The normal ORM flush guard handles tenant stamping and cross-tenant checks.

The examples use `strict=True` to deny reads when a scoped model has no rule.
The default mode allows tenant-wide reads for such models. Raw SQL, bulk DML,
unbound sessions, and bypass blocks are outside automatic enforcement.

[Understand the security boundary →](THREAT_MODEL.md)

## Find your next step

| You want to… | Read |
| --- | --- |
| Install the right database driver | [Installation](installation.md) |
| See a working example end to end | [Quickstart](quickstart.md) |
| Add roles, create rules, or custom tenant fields | [Writing policies](policies.md) |
| Bind an actor to every API request | [FastAPI integration](fastapi.md) |
| Understand a denied request or an open model | [Debugging policies](debugging.md) |
| Bring an existing Polar policy | [Migrating from Oso](MIGRATING_FROM_OSO.md) |
| Check signatures and available methods | [API reference](reference.md) |
