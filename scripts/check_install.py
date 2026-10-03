"""Check an installed distribution, its optional adapters, and release version."""

from __future__ import annotations

import os
from importlib.metadata import distribution
from importlib.resources import files

import aiosqlite  # noqa: F401
import asyncpg  # noqa: F401

import purview
from purview.fastapi import context_binder  # noqa: F401
from purview.sqlalchemy import install  # noqa: F401

dist = distribution("purview-authz")
tag = os.environ.get("RELEASE_TAG")
if tag and dist.version != tag.removeprefix("v"):
    raise RuntimeError(f"Installed {dist.version}, expected {tag}")
if purview.__version__ != dist.version:
    raise RuntimeError("Imported package and distribution versions disagree")
if not files("purview").joinpath("py.typed").is_file():
    raise RuntimeError("Wheel is missing the PEP 561 typing marker")
print(f"Installed purview-authz {dist.version}: core, FastAPI, SQLite, PostgreSQL, typing OK")
