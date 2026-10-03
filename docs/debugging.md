# Debugging policies

Purview provides two inspection tools that do not query the database: `explain()`
shows the compiled predicates, and `audit()` classifies model visibility.

## Explain a permission

Using the model and policy from the [quickstart](quickstart.md):

```python
ctx = Context(user_id=42, tenant_id=1, roles={"author"})
explanation = pv.explain(ctx, READ, Post)
print(explanation)
```

The output includes the effective roles, governing action, tenant SQL, row SQL,
combined predicate, and each registered rule's contribution. You can also pass a
bound session:

```python
explanation = pv.explain(session, "update", Post)
print(explanation.governing_action)  # 'read' if no update rule exists
print(explanation.combined_sql)
```

Explanation compiles expressions for inspection. It does not prove that a row
exists or evaluate an authorization result. SQL literal rendering is best effort.
Because the output can contain user and tenant identifiers, keep it in appropriate
development or diagnostic logs.

## Audit model visibility

```python
report = pv.audit()
print(report)
print(report.tenant_wide_models)
```

| Classification | Meaning |
| --- | --- |
| `global` | Exempt from automatic tenant and row filtering |
| `ruled` | Has registered read rules |
| `tenant-wide` | No read rule, and strict mode is off |
| `default-deny` | No read rule, and strict mode is on |

An audit reports policy configuration, not whether a particular actor is permitted.
A `ruled` model can still have a very permissive rule.

To surface tenant-wide models during startup:

```python
pv = install(Base, policy, audit="warn")
# Or fail startup if any scoped model is tenant-wide:
pv = install(Base, policy, audit="raise")
```

Choose one installation configuration for your app. `audit="raise"` raises
`PolicyAuditError` before attaching event listeners. With `strict=True`, models
without read rules are denied, so they are not flagged as tenant-wide.

## Warn about unfiltered operations

```python
pv = install(Base, policy, strict=True, warn_on_unfiltered=True)
```

Warnings can help find recognized unbound reads and raw/non-ORM statements on bound
sessions. They are advisory. They do not turn unsupported operations into protected
ones, and their absence does not establish enforcement. Review the
[security boundary](THREAT_MODEL.md) when choosing query patterns.

## Common surprises

| Symptom | Check |
| --- | --- |
| A query returns no rows | Confirm tenant, roles, registered read rules, and strict mode with `explain()` |
| Everyone in a tenant can read a model | Add a read rule or enable strict mode, then inspect `audit()` |
| An update is permitted despite no update rule | Actions without rules fall back to `read` |
| A new object passes despite no create role | Register and explicitly call a create rule through `validate_create()` |
| An async relationship raises `MissingGreenlet` | Use `selectinload()` or `awaitable_attrs` |
| `TenantMismatch` appears | Create a new session for the new tenant |
| `UnscopedModel` appears at startup | Add/configure the tenant field, or intentionally mark the model global |
| A loaded object remains accessible after a role change | Use a new session and context for the changed actor or permissions |

## Bypass for trusted maintenance

```python
from purview.sqlalchemy import bypass

with bypass(reason="nightly billing rollup"):
    # Use a dedicated maintenance session here.
    ...
```

The reason must be non-empty and is logged at warning level. Automatic guards are
suspended within the context. Do not reuse objects or sessions loaded under bypass
for ordinary requests. Async child tasks inherit context variables, so do not spawn
request work inside a bypass block.
