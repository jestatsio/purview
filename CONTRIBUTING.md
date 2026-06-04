# Contributing

Thanks for your interest in Purview. This is a security-sensitive library, so the
bar is **correctness and clarity over features** — and the default is always deny.

## Development setup

Purview uses [uv](https://docs.astral.sh/uv/); no manual virtualenv is needed:

```bash
uv run --extra dev pytest          # unit + integration + the example app
uv run --extra dev mypy            # strict typing is a project invariant
uv run --extra dev ruff check .    # lint
uv run --extra dev ruff format .   # format
```

### Running against Postgres

The integration suite parametrizes over SQLite and Postgres. SQLite runs by
default; to include Postgres, point `PURVIEW_TEST_POSTGRES_URL` at a database:

```bash
export PURVIEW_TEST_POSTGRES_URL=postgresql+asyncpg://user:pass@localhost/purview_test
uv run --extra dev pytest tests/integration
```

## Expectations for changes

- **Tests first for behaviour changes.** New enforcement behaviour needs a test
  that fails without the change. Leak-prevention tests belong in
  [`tests/integration/test_adversarial.py`](tests/integration/test_adversarial.py)
  and should be framed as an attacker trying to cross the tenant boundary.
- **`mypy --strict` and `ruff` must pass.** Type-correctness is a feature here.
- **Keep the core pure.** `purview.core` must not import the ORM-execution or web
  layers — that separation is what keeps policy logic unit-testable.
- **Default deny.** Anything that could widen access by accident is a bug, not a
  convenience.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
`test:`, `docs:`, `ci:`, `refactor:`, `chore:`.

## Releases

Maintainers cut releases by pushing a `v*` tag — see [RELEASING.md](RELEASING.md).
The version is derived from the tag; there is nothing to bump by hand.
