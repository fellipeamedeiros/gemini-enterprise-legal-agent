"""Gemini Enterprise Legal & Contract Redlining Agent (google-genai SDK).

Combines live Gemini Function Calling with:
1. RBAC-enforced Legal Playbook grounding (`search_legal_playbook`)
2. Deterministic clause risk & approval-tier scoring (`evaluate_clause_risk`)
3. Human-in-the-Loop (HITL) redline staging (`stage_redline_approval`)
"""

from __future__ import annotations

import os
import time
from typing import Any

from google import genai
from google.genai import types

from app.approval_store import ApprovalStore
from app.playbook import VALID_ROLES, search_legal_playbook

DEFAULT_MODEL = "gemini-3-flash-preview"
MAX_TOOL_ROUNDS = 10


class AgentConfigurationError(RuntimeError):
    """Raised when Vertex AI or Gemini API credentials are not configured."""


def evaluate_clause_risk(
    clause_category: str,
    contract_value_usd: float,
    deviation_severity: str,
) -> dict[str, Any]:
    """Deterministically score legal/financial risk and required approver tier."""
    sev = deviation_severity.upper()
    if sev not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        sev = "HIGH"

    multiplier = {"LOW": 0.05, "MEDIUM": 0.2, "HIGH": 0.5, "CRITICAL": 1.0}[sev]
    estimated_exposure = round(float(contract_value_usd) * multiplier, 2)

    if sev == "CRITICAL" or (sev == "HIGH" and contract_value_usd >= 500000):
        required_approver = "General Counsel / VP Legal (general_counsel)"
    elif sev in {"HIGH", "MEDIUM"}:
        required_approver = "Senior Legal Counsel (legal_counsel)"
    else:
        required_approver = "Standard Playbook Fallback (legal_counsel review)"

    return {
        "clause_category": clause_category,
        "contract_value_usd": round(float(contract_value_usd), 2),
        "risk_level": sev,
        "estimated_exposure_usd": estimated_exposure,
        "required_approver": required_approver,
    }


def _build_tool_declarations() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="search_legal_playbook",
                    description=(
                        "Search the corporate Legal Redline Playbook (RBAC-enforced for the "
                        "caller's role) to retrieve standard positions, fallback limits, and "
                        "approved redline wording for Liability, LGPD Privacy, Auto-Renewal, "
                        "IP/AI Ownership, Jurisdiction, and Restricted Executive Exceptions."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING,
                                description="Legal topic keywords (e.g., 'liability cap', 'LGPD breach', 'auto-renewal', 'IP AI training').",
                            ),
                        },
                        required=["query"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="evaluate_clause_risk",
                    description=(
                        "Deterministically compute risk level, estimated USD exposure, and "
                        "mandatory human approver tier for a contract clause deviation."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "clause_category": types.Schema(type=types.Type.STRING),
                            "contract_value_usd": types.Schema(type=types.Type.NUMBER),
                            "deviation_severity": types.Schema(
                                type=types.Type.STRING,
                                description="One of: LOW, MEDIUM, HIGH, CRITICAL",
                            ),
                        },
                        required=["clause_category", "contract_value_usd", "deviation_severity"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="stage_redline_approval",
                    description=(
                        "Stage a proposed contract redline in the Human-in-the-Loop (HITL) "
                        "Legal Approval Queue with status PENDING_APPROVAL. Always call this "
                        "for every HIGH or CRITICAL non-compliant clause you identify."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "contract_id": types.Schema(type=types.Type.STRING),
                            "counterparty": types.Schema(type=types.Type.STRING),
                            "clause_title": types.Schema(type=types.Type.STRING),
                            "risk_level": types.Schema(
                                type=types.Type.STRING,
                                description="One of: LOW, MEDIUM, HIGH, CRITICAL",
                            ),
                            "playbook_rule_id": types.Schema(
                                type=types.Type.STRING,
                                description="Cited playbook rule ID (e.g., PLAY-001).",
                            ),
                            "original_text": types.Schema(type=types.Type.STRING),
                            "proposed_redline": types.Schema(type=types.Type.STRING),
                            "rationale": types.Schema(type=types.Type.STRING),
                        },
                        required=[
                            "contract_id",
                            "counterparty",
                            "clause_title",
                            "risk_level",
                            "playbook_rule_id",
                            "original_text",
                            "proposed_redline",
                            "rationale",
                        ],
                    ),
                ),
            ]
        )
    ]


class GeminiEnterpriseLegalAgent:
    """Orchestrates RBAC-governed contract auditing & HITL redline staging."""

    def __init__(self, approval_store: ApprovalStore) -> None:
        self.approval_store = approval_store
        self.model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

    def get_auth_status(self) -> dict[str, Any]:
        use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes")
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        api_key = os.getenv("GEMINI_API_KEY")

        if use_vertex and project:
            return {
                "ready": True,
                "mode": "vertex_ai",
                "project": project,
                "location": location,
                "model": self.model,
            }
        if api_key:
            return {
                "ready": True,
                "mode": "gemini_api_key",
                "project": project,
                "location": None,
                "model": self.model,
            }
        return {
            "ready": False,
            "mode": "unconfigured",
            "project": project,
            "location": location,
            "model": self.model,
            "setup_hint": (
                "Export GOOGLE_GENAI_USE_VERTEXAI=true and GOOGLE_CLOUD_PROJECT=<your-project> "
                "(with gcloud ADC), OR export GEMINI_API_KEY=<your-key>."
            ),
        }

    def _create_client(self) -> genai.Client:
        status = self.get_auth_status()
        if not status["ready"]:
            raise AgentConfigurationError(status["setup_hint"])
        if status["mode"] == "vertex_ai":
            return genai.Client(
                vertexai=True,
                project=status["project"],
                location=status["location"],
            )
        return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def _build_system_instruction(self, user_role: str) -> str:
        role_label = VALID_ROLES.get(user_role, "Commercial Sales Rep")
        return (
            f"You are the Gemini Enterprise Legal & Contract Redlining Agent operating on behalf "
            f"of a user with RBAC persona: **{role_label}** (`{user_role}`).\n\n"
            "Your workflow:\n"
            "1. Always call `search_legal_playbook` FIRST to ground your audit in official corporate "
            "playbook rules (`PLAY-001`..`PLAY-006`). Respect RBAC: if `rbac_redacted_count > 0`, "
            "explicitly inform the user that restricted executive/legal policy documents were withheld "
            "under RBAC for their persona and never speculate about restricted contents.\n"
            "2. For every non-compliant clause in a contract draft, call `evaluate_clause_risk` to "
            "quantify exposure and determine the required human approver.\n"
            "3. For every HIGH or CRITICAL deviation in a contract draft, call `stage_redline_approval` "
            "so the proposed redline enters the Human-in-the-Loop Legal Approval Queue (`PENDING_APPROVAL`).\n"
            "4. Present a crisp, executive-ready Markdown report with: Risk Summary, Clause-by-Clause "
            "Playbook Findings (citing `rule_id`), Staged Redline IDs (`RED-...`), and Next Steps for "
            "Human Legal Sign-Off."
        )

    def _dispatch_tool(self, name: str, args: dict[str, Any], user_role: str) -> dict[str, Any]:
        if name == "search_legal_playbook":
            return search_legal_playbook(args.get("query", ""), user_role=user_role)
        if name == "evaluate_clause_risk":
            return evaluate_clause_risk(
                clause_category=str(args.get("clause_category", "General")),
                contract_value_usd=float(args.get("contract_value_usd", 0)),
                deviation_severity=str(args.get("deviation_severity", "HIGH")),
            )
        if name == "stage_redline_approval":
            return self.approval_store.stage_redline(
                contract_id=str(args.get("contract_id", "CTR-CUSTOM")),
                counterparty=str(args.get("counterparty", "Counterparty")),
                clause_title=str(args.get("clause_title", "Clause")),
                risk_level=str(args.get("risk_level", "HIGH")),
                playbook_rule_id=str(args.get("playbook_rule_id", "PLAY-001")),
                original_text=str(args.get("original_text", "")),
                proposed_redline=str(args.get("proposed_redline", "")),
                rationale=str(args.get("rationale", "")),
            )
        return {"error": f"Unknown tool: {name}"}

    def audit_or_ask(
        self,
        prompt: str,
        user_role: str = "sales_rep",
        contract_id: str | None = None,
        counterparty: str | None = None,
        contract_value_usd: float | None = None,
        contract_text: str | None = None,
    ) -> dict[str, Any]:
        """Run the multi-step Gemini tool-calling loop with RBAC & HITL staging."""
        t0 = time.perf_counter()
        role = user_role if user_role in VALID_ROLES else "sales_rep"
        client = self._create_client()
        tools = _build_tool_declarations()
        config = types.GenerateContentConfig(
            system_instruction=self._build_system_instruction(role),
            tools=tools,
            temperature=0.1,
        )

        full_user_prompt = prompt
        if contract_text:
            full_user_prompt = (
                f"{prompt}\n\n"
                f"Contract Metadata: contract_id={contract_id or 'CTR-CUSTOM'}, "
                f"counterparty={counterparty or 'Counterparty'}, "
                f"contract_value_usd={contract_value_usd or 250000}\n\n"
                f"Contract Text:\n{contract_text}"
            )

        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part.from_text(text=full_user_prompt)])
        ]
        trace: list[dict[str, Any]] = []
        final_text = ""

        for round_idx in range(1, MAX_TOOL_ROUNDS + 1):
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content or not candidate.content.parts:
                break

            contents.append(candidate.content)
            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if getattr(part, "function_call", None)
            ]

            if not function_calls:
                final_text = response.text or ""
                break

            tool_response_parts: list[types.Part] = []
            for fc in function_calls:
                call_start = time.perf_counter()
                fc_args = dict(fc.args) if fc.args else {}
                result = self._dispatch_tool(fc.name, fc_args, user_role=role)
                duration_ms = round((time.perf_counter() - call_start) * 1000, 1)
                trace.append(
                    {
                        "round": round_idx,
                        "tool": fc.name,
                        "arguments": fc_args,
                        "status": "error" if "error" in result else "ok",
                        "duration_ms": duration_ms,
                        "result": result,
                    }
                )
                tool_response_parts.append(
                    types.Part.from_function_response(name=fc.name, response=result)
                )

            contents.append(types.Content(role="user", parts=tool_response_parts))

        return {
            "caller_role": role,
            "answer_markdown": final_text,
            "trace": trace,
            "model": self.model,
            "total_duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
