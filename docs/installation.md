# Installation

Purview runs on **Python 3.11 or newer**. The published **0.3.1** release supports
**SQLAlchemy 2.0** (`>=2.0,<2.1`). Install `purview-authz` and import `purview`.

The development branch targets **SQLAlchemy 2.1** (`>=2.1.1,<2.2`). Installing from
source therefore uses a different dependency range from the current PyPI release.

## Choose your setup

=== "uv"

    In an existing project:

    ```bash
    uv add "purview-authz[sqlite]"
    ```

    Or create a new project first:

    ```bash
    uv init my-purview-app
    cd my-purview-app
    uv add "purview-authz[sqlite]"
    ```

=== "pip"

    Create and activate a virtual environment:

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install "purview-authz[sqlite]"
    ```

    On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead.

The SQLite extra is enough to run the [quickstart](quickstart.md). No database server
or API credentials are needed.

## Extras and database drivers

| Package | What it adds | SQLAlchemy connection URL |
| --- | --- | --- |
| `purview-authz` | SQLAlchemy with asyncio support | Supply your own driver |
| `purview-authz[sqlite]` | `aiosqlite` | `sqlite+aiosqlite:///app.db` |
| `purview-authz[postgres]` | `asyncpg` | `postgresql+asyncpg://user:password@localhost/app` |
| `purview-authz[fastapi]` | FastAPI | Supply your own driver |
| `purview-authz[fastapi,postgres]` | FastAPI and `asyncpg` | PostgreSQL |

Extras compose. For a FastAPI application using SQLite:

```bash
uv add "purview-authz[fastapi,sqlite]"
```

An ASGI server is separate from the FastAPI adapter. Install one if your app needs
it, for example `uv add "uvicorn[standard]"`.

Purview does not provision a database or manage your schema. Continue using your
application's migrations and SQLAlchemy engine configuration. The
[tracker example](https://github.com/jestatsio/purview/tree/main/examples/tracker)
shows a PostgreSQL application with Alembic migrations.

## Verify the installation

=== "uv"

    ```bash
    uv run python -c "import purview; print(purview.__version__)"
    ```

=== "pip"

    ```bash
    python -c "import purview; print(purview.__version__)"
    ```

If the module is missing, make sure you installed into the same environment used
to run Python. A missing `aiosqlite` or `asyncpg` import means the matching driver
extra is needed.

## Develop from source

```bash
git clone https://github.com/jestatsio/purview.git
cd purview
uv sync --locked --all-extras
uv run --locked --all-extras pytest
uv run --locked --all-extras mkdocs serve
```

See the [contributor guide](https://github.com/jestatsio/purview/blob/main/CONTRIBUTING.md)
for linting, typing, and PostgreSQL validation.

[Continue to the quickstart →](quickstart.md)
