"""Engine + sessionmaker, configured from ``DATABASE_URL``."""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/tracker"
)

# NullPool keeps the example robust across event loops (e.g. the test suite). For a
# long-running server, drop NullPool and configure a real connection pool instead.
engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
