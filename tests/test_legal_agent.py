"""Automated verification suite for Gemini Enterprise Legal & Contract Redlining Agent."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent import evaluate_clause_risk
from app.approval_store import ApprovalStore, RBACPermissionError
from app.main import app
from app.playbook import list_playbook_for_role, search_legal_playbook


def test_rbac_hides_restricted_ma_policy_from_sales_rep() -> None:
    sales_view = list_playbook_for_role("sales_rep")
    legal_view = list_playbook_for_role("legal_counsel")

    assert sales_view["rbac_hidden_count"] == 1
    assert legal_view["rbac_hidden_count"] == 0
    assert all(r["rule_id"] != "PLAY-006" for r in sales_view["rules"])
    assert any(r["rule_id"] == "PLAY-006" for r in legal_view["rules"])

    sales_search = search_legal_playbook("Project Aurora M&A indemnity 3x exception", user_role="sales_rep")
    assert sales_search["rbac_redacted_count"] == 1
    assert all(r["rule_id"] != "PLAY-006" for r in sales_search["rules"])

    gc_search = search_legal_playbook("Project Aurora M&A indemnity 3x exception", user_role="general_counsel")
    assert gc_search["rbac_redacted_count"] == 0
    assert gc_search["rules"][0]["rule_id"] == "PLAY-006"


def test_risk_evaluator_assigns_correct_approver_tiers() -> None:
    crit = evaluate_clause_risk("Liability", 450000.0, "CRITICAL")
    assert crit["risk_level"] == "CRITICAL"
    assert crit["estimated_exposure_usd"] == 450000.0
    assert "General Counsel" in crit["required_approver"]

    high_mid = evaluate_clause_risk("Commercial Terms", 200000.0, "HIGH")
    assert high_mid["estimated_exposure_usd"] == 100000.0
    assert "Senior Legal Counsel" in high_mid["required_approver"]


def test_hitl_approval_store_enforces_rbac(tmp_path: Path) -> None:
    store = ApprovalStore(db_path=tmp_path / "approvals.db")
    staged = store.stage_redline(
        contract_id="CTR-TEST-01",
        counterparty="Apex Data",
        clause_title="Section 7 — Unlimited Liability",
        risk_level="CRITICAL",
        playbook_rule_id="PLAY-001",
        original_text="Customer liability is UNLIMITED.",
        proposed_redline="Liability capped at 12 months fees.",
        rationale="Violates PLAY-001.",
    )
    aid = staged["approval_id"]
    assert staged["status"] == "PENDING_APPROVAL"

    # Sales Rep cannot approve.
    with pytest.raises(RBACPermissionError):
        store.decide_approval(aid, "APPROVED", caller_role="sales_rep")

    # Senior Legal Counsel cannot approve a CRITICAL deviation.
    with pytest.raises(RBACPermissionError):
        store.decide_approval(aid, "APPROVED", caller_role="legal_counsel")

    # General Counsel can approve CRITICAL deviation.
    approved = store.decide_approval(aid, "APPROVED", caller_role="general_counsel")
    assert approved["status"] == "APPROVED"
    assert approved["decided_by_role"] == "general_counsel"


def test_fastapi_openapi_and_endpoints() -> None:
    client = TestClient(app)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["connector_spec"] == "/openapi.json"

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/ge/audit-contract" in paths
    assert "/api/ge/approvals" in paths
    assert "/api/ge/approvals/{approval_id}/decide" in paths

    boot = client.get("/api/bootstrap?user_role=sales_rep")
    assert boot.status_code == 200
    assert boot.json()["playbook"]["rbac_hidden_count"] == 1
