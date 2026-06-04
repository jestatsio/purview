"""A small multi-tenant project tracker — the Purview dogfood schema.

Deliberately exercises every 0.2 capability:

* ``Workspace`` is the tenant root (global); ``User`` is global.
* ``Membership`` has a **composite primary key** (workspace + user).
* ``Task`` has a **UUID primary key**.
* ``LegacyImport`` is scoped by a **different tenant column** (``account_id``) —
  a table imported from an older system that didn't use ``workspace_id``.
* Everything else is tenant-scoped by ``workspace_id`` (the install default).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Workspace(Base):  # the tenant root — global
    __tablename__ = "workspace"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class User(Base):  # global (a user may belong to many workspaces)
    __tablename__ = "app_user"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Membership(Base):  # composite PK; tenant column = workspace_id
    __tablename__ = "membership"
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspace.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("app_user.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))  # "admin" | "member"


class Project(Base):  # tenant-scoped by workspace_id (the install default)
    __tablename__ = "project"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(String(100))


class Task(Base):  # UUID PK; tenant-scoped by workspace_id
    __tablename__ = "task"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    assignee_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(200))


class LegacyImport(Base):  # scoped by a legacy column name: account_id
    __tablename__ = "legacy_import"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid)  # == the workspace id
    payload: Mapped[str] = mapped_column(String(200))
