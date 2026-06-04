"""Secure-by-default: a non-global model without the tenant column is rejected at
install() time (fail closed), never shipped unscoped."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from purview import Policy
from purview.exceptions import UnscopedModel
from purview.sqlalchemy import install


def test_unscoped_model_raises_at_install() -> None:
    class B(DeclarativeBase):
        pass

    class Scoped(B):
        __tablename__ = "scoped_ok"
        id: Mapped[int] = mapped_column(primary_key=True)
        org_id: Mapped[int] = mapped_column()

    class Unscoped(B):  # no org_id, not marked global → must fail closed
        __tablename__ = "unscoped_bad"
        id: Mapped[int] = mapped_column(primary_key=True)

    with pytest.raises(UnscopedModel, match="Unscoped"):
        install(B, Policy(), tenant_column="org_id")


def test_global_marker_allows_install() -> None:
    class B(DeclarativeBase):
        pass

    class Scoped(B):
        __tablename__ = "scoped_ok2"
        id: Mapped[int] = mapped_column(primary_key=True)
        org_id: Mapped[int] = mapped_column()

    class Reference(B):
        __tablename__ = "reference2"
        id: Mapped[int] = mapped_column(primary_key=True)

    policy = Policy()
    policy.global_model(Reference)
    pv = install(B, policy, tenant_column="org_id")
    try:
        assert Scoped in pv.scoped
        assert Reference not in pv.scoped
    finally:
        pv.uninstall()
