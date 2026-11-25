#!/usr/bin/env python3
"""Step 3 (ADK Option): Deploy the Legal & Contract Redlining Agent to Vertex AI Agent Engine.

Self-contained deployment script: loads the playbook data from `app/playbook.py`
at deploy time and embeds pure-Python tool functions so the remote Vertex AI
Agent Engine container has zero local-module import dependencies.

Usage:
  export GOOGLE_CLOUD_PROJECT="your-project-id"
  export VERTEX_REGION="us-central1"
  export STAGING_BUCKET="gs://your-project-id-ge-legal-playbook"
  python3 scripts/03_deploy_adk_agent_engine.py
"""

from __future__ import annotations

import importlib.metadata
import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


def main() -> None:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    region = os.environ.get("VERTEX_REGION", "us-central1")
    staging_bucket = os.environ.get("STAGING_BUCKET")
    model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

    if not project_id:
        raise SystemExit("ERROR: Set GOOGLE_CLOUD_PROJECT before running this script.")
    if not staging_bucket:
        staging_bucket = f"gs://{project_id}-ge-legal-playbook"

    # Load plain data structures at deploy time so cloudpickle needs zero local imports.
    from app.playbook import LEGAL_PLAYBOOK, VALID_ROLES

    playbook_data = [dict(rule) for rule in LEGAL_PLAYBOOK]
    valid_roles = dict(VALID_ROLES)

    import vertexai
    from google.adk.agents import LlmAgent
    from vertexai import agent_engines
    from vertexai.preview.reasoning_engines import AdkApp

    def audit_playbook_rule(query: str, user_role: str = "sales_rep") -> dict:
        """Search the corporate Legal Redline Playbook enforcing RBAC for the user role."""
        role = user_role if user_role in valid_roles else "sales_rep"
        tokens = [t for t in re.findall(r"[a-z0-9_&]+", query.lower()) if len(t) >= 2]
        scored = []
        rbac_filtered_count = 0

        for rule in playbook_data:
            haystack = " ".join(
                [
                    rule["rule_id"],
                    rule["title"],
                    rule["category"],
                    " ".join(rule["tags"]),
                    rule["standard_position"],
                    rule["fallback_position"],
                ]
            ).lower()
            score = sum(
                3 if t in rule["tags"] else (2 if t in rule["title"].lower() else 1)
                for t in tokens
                if t in haystack
            )
            if score > 0 or not tokens:
                if role not in rule["allowed_roles"]:
                    rbac_filtered_count += 1
                    continue
                scored.append((score, rule))

        scored.sort(key=lambda item: item[0], reverse=True)
        matches = [
            {
                "rule_id": r["rule_id"],
                "title": r["title"],
                "category": r["category"],
                "standard_position": r["standard_position"],
                "fallback_position": r["fallback_position"],
                "redline_template": r["redline_template"],
                "relevance_score": score,
            }
            for score, r in scored[:4]
        ]
        return {
            "query": query,
            "caller_role": role,
            "match_count": len(matches),
            "rbac_redacted_count": rbac_filtered_count,
            "rules": matches,
        }

    def score_clause_risk(
        clause_category: str,
        contract_value_usd: float,
        deviation_severity: str,
    ) -> dict:
        """Compute legal/financial risk exposure and mandatory human approver tier."""
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

    def stage_hitl_redline(
        contract_id: str,
        counterparty: str,
        clause_title: str,
        risk_level: str,
        playbook_rule_id: str,
        original_text: str,
        proposed_redline: str,
        rationale: str,
    ) -> dict:
        """Stage a contract redline proposal for mandatory human Legal Counsel sign-off."""
        return {
            "status": "PENDING_APPROVAL",
            "contract_id": contract_id,
            "counterparty": counterparty,
            "clause_title": clause_title,
            "risk_level": risk_level.upper(),
            "playbook_rule_id": playbook_rule_id,
            "original_text": original_text,
            "proposed_redline": proposed_redline,
            "rationale": rationale,
            "governance_note": (
                "Staged for Human-in-the-Loop Legal Counsel approval. "
                "AI agents never self-approve external contract modifications."
            ),
        }

    root_agent = LlmAgent(
        name="legal_contract_redlining_agent",
        model=model,
        description=(
            "Audits enterprise MSAs, NDAs, and LGPD DPAs against the corporate Legal Playbook "
            "with RBAC enforcement, deterministic risk scoring, and HITL redline staging."
        ),
        instruction=(
            "You are the Gemini Enterprise Legal & Contract Redlining Agent. "
            "1. Always call `audit_playbook_rule` first to ground findings in corporate playbook rules "
            "(PLAY-001..PLAY-006). Respect RBAC redactions and never speculate about restricted rules. "
            "2. Call `score_clause_risk` for every non-compliant clause. "
            "3. Call `stage_hitl_redline` for every HIGH or CRITICAL deviation. "
            "4. Return a concise executive Markdown summary citing rule IDs and required human approvers."
        ),
        tools=[audit_playbook_rule, score_clause_risk, stage_hitl_redline],
    )

    print(f"Initializing Vertex AI (project={project_id}, region={region}, staging={staging_bucket})...")
    vertexai.init(project=project_id, location=region, staging_bucket=staging_bucket)

    adk_version = importlib.metadata.version("google-adk")
    aiplatform_version = importlib.metadata.version("google-cloud-aiplatform")

    adk_app = AdkApp(agent=root_agent, enable_tracing=True)
    remote_agent = agent_engines.create(
        adk_app,
        display_name="Legal & Contract Redlining Agent",
        description="Gemini Enterprise ADK Agent for MSA/NDA/DPA Playbook Auditing & HITL Redlining",
        env_vars={"GOOGLE_CLOUD_LOCATION": "global"},
        requirements=[
            f"google-cloud-aiplatform[adk,agent_engines]=={aiplatform_version}",
            f"google-adk=={adk_version}",
        ],
    )

    resource_name = remote_agent.resource_name
    print("\n=== Deployed to Vertex AI Agent Engine ===")
    print(f"REASONING_ENGINE_RESOURCE={resource_name}")

    env_file = ROOT_DIR / ".ge_env"
    with env_file.open("a", encoding="utf-8") as f:
        f.write(f"REASONING_ENGINE_RESOURCE={resource_name}\n")
    print(f"Appended REASONING_ENGINE_RESOURCE to {env_file}")


if __name__ == "__main__":
    main()
