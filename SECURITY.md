# Security Policy

Purview is an authorization library: a defect can mean a cross-tenant data leak.
Security reports are taken seriously and handled promptly.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

Until 1.0, only the latest released 0.x line receives security fixes.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub's
[private vulnerability reporting](https://github.com/jestatsio/purview/security/advisories/new)
(the **Report a vulnerability** button on the repository's Security tab). Please
include:

- a description of the issue and its impact (e.g. cross-tenant read or write),
- a minimal reproduction — the models, the policy, and the query or request,
- the affected version(s).

You can expect an acknowledgement within a few days. Once a fix is ready a new
patch release is published and the advisory is disclosed, with credit unless you
prefer to remain anonymous.

## Scope

**In scope** — any way to read or write rows across the tenant boundary, or to
bypass a registered policy, through the supported ORM surface (`select`,
`Session.get`, relationship loads, and flush) on a context-bound session.

**Out of scope** — behaviour documented as outside the enforcement boundary:
raw SQL and Core `text()`, unbound sessions, and explicit `bypass(...)` blocks.
See [the enforcement boundary](README.md#the-enforcement-boundary).
