# Contributing to Purview

Purview handles authorization and tenant isolation. Changes should make its behavior
more predictable, easier to inspect, and harder to misuse.

## Set up a checkout

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python
3.11 or newer, then run:

```bash
git clone https://github.com/jestatsio/purview.git
cd purview
uv sync --locked --all-extras
```

This installs the local package, test tools, documentation tools, database drivers,
and tracker dependencies into `.venv`.

## Validate a change

```bash
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy
uv run --locked --all-extras pytest tests examples/tracker/test_smoke.py --cov=purview --cov-fail-under=90
uv run --locked --all-extras python examples/quickstart.py
uv run --locked --all-extras mkdocs build --strict
```

Use `ruff format .` to apply formatting. Preview documentation with
`uv run --locked --all-extras mkdocs serve`.

SQLite tests work without a database server. For the PostgreSQL suite, point
`PURVIEW_TEST_POSTGRES_URL` at a **dedicated, disposable test database**:

```bash
export PURVIEW_TEST_POSTGRES_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/purview_test
uv run --locked --all-extras pytest tests examples/tracker/test_smoke.py
```

The integration fixtures recreate their tables in that database. The tracker tests
use temporary SQLite files and separate PostgreSQL schemas. They ignore the demo's
`DATABASE_URL`. CI runs both backends on Python 3.11, 3.12, 3.13, and 3.14.

## Expectations

- Add a failing regression before fixing enforcement behavior. Test both an allowed
  operation and the denied or cross-tenant case.
- Keep `purview.core` free of ORM execution and web-framework imports.
- Keep checks and query filtering consistent. Document defaults accurately:
  registered read rules deny when they return no grants, while scoped models with
  no read rule remain tenant-wide unless `strict=True` is enabled.
- Make changes to public behavior visible in `CHANGELOG.md` and the relevant guide.
- Keep dependency changes in `pyproject.toml` and regenerate `uv.lock` with `uv lock`.
  Use `uv lock --upgrade` for a deliberate refresh, then run the full checks.
- Report vulnerabilities through [private security reporting](SECURITY.md).

Use conventional commit prefixes such as `fix:`, `feat:`, `docs:`, `test:`, and
`ci:`. See [RELEASING.md](RELEASING.md) for the maintainer release process.
