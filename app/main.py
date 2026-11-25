"""FastAPI server & Gemini Enterprise OpenAPI 3.0 Custom Action Connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agent import AgentConfigurationError, GeminiEnterpriseLegalAgent
from app.approval_store import ApprovalStore, RBACPermissionError
from app.playbook import SAMPLE_CONTRACTS, VALID_ROLES, list_playbook_for_role

STATIC_DIR = Path(__file__).resolve().parent / "static"

approval_store = ApprovalStore()
legal_agent = GeminiEnterpriseLegalAgent(approval_store)

app = FastAPI(
    title="Gemini Enterprise — Legal & Contract Redlining Agent",
    description=(
        "Python + FastAPI + Gemini Enterprise Custom Action Connector (OpenAPI 3.0) "
        "for MSA/NDA/DPA Playbook Auditing, RBAC Enforcement, and HITL Redline Approvals."
    ),
    version="1.0.0",
)


class AuditRequest(BaseModel):
    prompt: str = Field(
        default="Audit this contract against our corporate Legal Playbook, quantify risk exposure, and stage redlines for all HIGH/CRITICAL deviations.",
        min_length=3,
        max_length=1500,
    )
    user_role: str = Field(default="sales_rep", description="RBAC role: sales_rep, legal_counsel, general_counsel")
    contract_id: str | None = None
    counterparty: str | None = None
    contract_value_usd: float | None = 250000.0
    contract_text: str | None = None


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="APPROVED or REJECTED")
    user_role: str = Field(..., description="Caller RBAC persona")
    reviewer_note: str = Field(default="", max_length=500)


@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/.well-known/agent.json", summary="A2A Agent Card for Gemini Enterprise Registration")
def a2a_agent_card(request: Request) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    return {
        "name": "Legal & Contract Redlining Agent",
        "description": (
            "Audits enterprise MSAs, NDAs, and LGPD DPAs against the corporate Legal Playbook "
            "with RBAC enforcement and HITL redline approvals."
        ),
        "url": base_url,
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "audit_contract",
                "name": "Audit & Redline Enterprise Contracts",
                "description": "Playbook-grounded risk evaluation and HITL redline staging.",
                "tags": ["legal", "contracts", "lgpd", "redlining", "rbac"],
            }
        ],
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "connector_spec": "/openapi.json",
        "roles": VALID_ROLES,
        "ai_auth": legal_agent.get_auth_status(),
    }


@app.get("/api/bootstrap")
def bootstrap(user_role: str = "sales_rep") -> dict[str, Any]:
    return {
        "roles": VALID_ROLES,
        "playbook": list_playbook_for_role(user_role),
        "sample_contracts": SAMPLE_CONTRACTS,
        "approvals": approval_store.list_approvals(),
        "ai_auth": legal_agent.get_auth_status(),
    }


@app.post("/api/ge/audit-contract", summary="Gemini Enterprise Custom Action: Audit & Stage Contract Redlines")
def audit_contract(req: AuditRequest) -> dict[str, Any]:
    try:
        result = legal_agent.audit_or_ask(
            prompt=req.prompt,
            user_role=req.user_role,
            contract_id=req.contract_id,
            counterparty=req.counterparty,
            contract_value_usd=req.contract_value_usd,
            contract_text=req.contract_text,
        )
        result["approvals"] = approval_store.list_approvals()
        return result
    except AgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Gemini Enterprise Agent error: {exc}") from exc


@app.get("/api/ge/approvals", summary="List HITL Legal Redline Approval Queue")
def list_approvals() -> dict[str, Any]:
    return {"approvals": approval_store.list_approvals()}


@app.post("/api/ge/approvals/{approval_id}/decide", summary="Human-in-the-Loop Legal Sign-Off (RBAC Enforced)")
def decide_approval(approval_id: str, req: ApprovalDecisionRequest) -> dict[str, Any]:
    try:
        updated = approval_store.decide_approval(
            approval_id=approval_id,
            decision=req.decision,
            caller_role=req.user_role,
            reviewer_note=req.reviewer_note,
        )
        return {"updated": updated, "approvals": approval_store.list_approvals()}
    except RBACPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
