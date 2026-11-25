# Gemini Enterprise — Legal & Contract Redlining Agent

A clean, stage-ready **Python + FastAPI + Google ADK + Gemini Enterprise** demo showcasing how **Gemini Enterprise (Agentic Workplace Transformation)** solves high-stakes enterprise legal and procurement workflows with **RBAC Policy Enforcement**, **Playbook-Grounded Redlining**, and **Human-in-the-Loop (HITL) Approvals**.

## The Enterprise Challenge

Enterprise Legal, Procurement, and Commercial teams lose weeks per deal manually reviewing third-party MSAs, NDAs, and LGPD DPAs against internal Legal Playbooks. Meanwhile, CISOs and General Counsel block generic AI tools because:
1. **No RBAC / ACLs**: Sales teams could accidentally surface confidential Board/M&A fallback thresholds.
2. **No Human-in-the-Loop Controls**: Autonomous AI must never approve or send external contract redlines without legal sign-off.
3. **No Auditability**: Legal teams need exact playbook rule citations and risk exposure math for every proposed edit.

## The Gemini Enterprise Python Solution

This repository includes:
1. **End-to-End Gemini Enterprise Provisioning & Registration Scripts (`scripts/`)**: Spin up a GCS Legal Playbook Data Store, create a **Gemini Enterprise App (`APP_TYPE_INTRANET`)**, deploy the Legal Redlining **Google ADK Agent** to **Vertex AI Agent Engine**, and register it directly inside your Gemini Enterprise App.
2. **Interactive Local/Cloud Run Web UI & OpenAPI 3.0 Connector (`app/`)**: Demonstrates live persona switching (`sales_rep`, `legal_counsel`, `general_counsel`), RBAC playbook redaction (`PLAY-006`), deterministic risk scoring, and a SQLite-backed HITL Legal Approval Queue enforcing HTTP 403 RBAC sign-off guardrails.

---

## Spin Up a Gemini Enterprise App & Register the Agent

```bash
git clone https://github.com/fellipeamedeiros/gemini-enterprise-legal-agent.git
cd gemini-enterprise-legal-agent
export GOOGLE_CLOUD_PROJECT="<YOUR_GCP_PROJECT_ID>"

# 1. Enable Discovery Engine, Vertex AI, Cloud Run, and IAM permissions
./scripts/01_enable_apis_and_iam.sh

# 2. Upload synthetic playbook docs to GCS, create Data Store, and create Gemini Enterprise App
./scripts/02_create_ge_app.sh

# 3A. Option A (ADK on Vertex AI Agent Engine — recommended for native GE ADK registration)
pip install "google-cloud-aiplatform[adk,agent_engines]>=1.95.0" google-adk
python3 scripts/03_deploy_adk_agent_engine.py
./scripts/04_register_agent_in_ge.sh --mode adk

# 3B. Option B (Cloud Run + A2A Agent Card registration)
./scripts/05_deploy_cloud_run.sh
./scripts/04_register_agent_in_ge.sh --mode a2a

# 4. Verify registered agents inside the Gemini Enterprise App
./scripts/04_register_agent_in_ge.sh --list
```

---

## Run Local Interactive Web UI & Tests

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="<YOUR_GCP_PROJECT_ID>"
export GOOGLE_CLOUD_LOCATION="global"
bash run_demo.sh
```

Open `http://localhost:8081` (and OpenAPI 3.0 docs at `http://localhost:8081/docs`).

Run automated unit & RBAC tests:
```bash
.venv/bin/python -m pytest -v tests/test_legal_agent.py
```

---

## 10-Minute Live Stage Demo Script

| Time | Segment | Live Action |
| :--- | :--- | :--- |
| **0:00–1:30** | **Hook & Workplace Challenge** | Frame the commercial bottleneck: Sales waits 2 weeks for Legal to review MSAs/NDAs/DPAs, while Legal demands RBAC & HITL governance. |
| **1:30–4:30** | **Demo Moment 1: Live MSA Playbook Audit** | Run **Prompt 1 (Enterprise MSA, \$450k)** as `sales_rep`. Watch Gemini call `audit_playbook_rule` (`PLAY-001`, `PLAY-002`, `PLAY-003`), `score_clause_risk`, and `stage_hitl_redline`. |
| **4:30–6:30** | **Demo Moment 2: Live RBAC Security Test** | Ask about restricted Project Aurora M&A 3x exceptions as `sales_rep` → show `rbac_redacted_count: 1` withholding `PLAY-006`. Switch to `general_counsel` → show authorized access. |
| **6:30–8:00** | **Demo Moment 3: HITL Approval Queue** | Attempt to approve a staged redline as `sales_rep` → live **HTTP 403 RBAC Denied**. Switch to `general_counsel` → `APPROVED` with audit timestamp. |
| **8:00–10:00** | **Gemini Enterprise Architecture & Scripts** | Show the live registered agent inside **Gemini Enterprise Apps Console** and walk through `scripts/02`–`04` and `app/agent.py`. |

> **Data Disclaimer**: All contracts, counterparties, and legal playbook rules in this repository are 100% synthetic data created for demonstration purposes.
