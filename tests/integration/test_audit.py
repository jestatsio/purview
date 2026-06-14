"""Purview.audit() classifies read-visibility; install(audit=...) surfaces
scoped models with no read rule at startup."""

from __future__ import annotations

import warnings

import pytest
from conftest import Env
from models import Base, build_policy

from purview import PolicyAuditError, PurviewWarning
from purview.sqlalchemy import install


async def test_audit_classifies_the_standard_policy(env: Env) -> None:
    report = env.pv.audit()
    visibility = {m.model: m.visibility for m in report.models}
    assert visibility["Post"] == "ruled"  # has a read rule
    assert visibility["Comment"] == "tenant-wide"  # no read rule, non-strict
    assert visibility["Animal"] == "tenant-wide"
    assert visibility["Org"] == "global"
    assert visibility["GlobalThing"] == "global"
    # Dog inherits Animal, so it is governed by the base mapper, not listed.
    assert "Dog" not in visibility

    flagged = {m.model for m in report.tenant_wide_models}
    assert {"Comment", "Animal"} <= flagged
    assert "Post" not in flagged and "Org" not in flagged


def test_install_audit_raise_rejects_tenant_wide_models() -> None:
    with pytest.raises(PolicyAuditError, match="tenant-wide"):
        install(Base, build_policy(), tenant_column="org_id", audit="raise")
    # A rejected install must not leave guards attached: a plain install now works.
    pv = install(Base, build_policy(), tenant_column="org_id")
    pv.uninstall()


def test_install_audit_warn_emits_one_warning() -> None:
    with pytest.warns(PurviewWarning, match="tenant-wide"):
        pv = install(Base, build_policy(), tenant_column="org_id", audit="warn")
    pv.uninstall()


def test_strict_install_audit_finds_nothing() -> None:
    # Under strict, unruled models default-deny rather than being tenant-wide.
    with warnings.catch_warnings():
        warnings.simplefilter("error", PurviewWarning)
        pv = install(Base, build_policy(), tenant_column="org_id", strict=True, audit="raise")
    assert pv.audit().tenant_wide_models == ()
    pv.uninstall()
