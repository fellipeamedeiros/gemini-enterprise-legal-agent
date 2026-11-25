#!/usr/bin/env bash
# Step 4: Register (or list/delete) the Legal & Contract Redlining Agent inside
# your Gemini Enterprise App (Discovery Engine v1alpha Assistant Agents API).
#
# Usage:
#   ./scripts/04_register_agent_in_ge.sh --mode adk   # Register Vertex AI Agent Engine (ADK)
#   ./scripts/04_register_agent_in_ge.sh --mode a2a   # Register Cloud Run A2A Agent
#   ./scripts/04_register_agent_in_ge.sh --list       # List registered agents in GE App
#   ./scripts/04_register_agent_in_ge.sh --delete <AGENT_ID>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${ROOT_DIR}/.ge_env" ]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.ge_env"
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "${PROJECT_ID}" ]; then
  echo "ERROR: Set GOOGLE_CLOUD_PROJECT or run scripts/02_create_ge_app.sh first." >&2
  exit 1
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
GE_LOCATION="${GE_LOCATION:-global}"
ENGINE_ID="${GE_ENGINE_ID:-legal-redline-ge-app}"
AGENT_DISPLAY_NAME="${AGENT_DISPLAY_NAME:-Legal & Contract Redlining Agent}"
AGENT_DESCRIPTION="${AGENT_DESCRIPTION:-Audits enterprise MSAs, NDAs, and LGPD DPAs against the corporate Legal Playbook with RBAC enforcement and HITL redline approvals.}"

if [ "${GE_LOCATION}" = "global" ]; then
  DE_HOST="discoveryengine.googleapis.com"
else
  DE_HOST="${GE_LOCATION}-discoveryengine.googleapis.com"
fi

AGENTS_URL="https://${DE_HOST}/v1alpha/projects/${PROJECT_NUMBER}/locations/${GE_LOCATION}/collections/default_collection/engines/${ENGINE_ID}/assistants/default_assistant/agents"
ACCESS_TOKEN="$(gcloud auth print-access-token)"

MODE="adk"
DELETE_ID=""
ACTION="register"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --list)
      ACTION="list"
      shift
      ;;
    --delete)
      ACTION="delete"
      DELETE_ID="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [ "${ACTION}" = "list" ]; then
  echo "=== Listing Agents registered in Gemini Enterprise App (${ENGINE_ID}) ==="
  curl -sS -X GET \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    "${AGENTS_URL}" | python3 -m json.tool
  exit 0
fi

if [ "${ACTION}" = "delete" ]; then
  echo "=== Deleting Agent ${DELETE_ID} from Gemini Enterprise App (${ENGINE_ID}) ==="
  curl -sS -X DELETE \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    "${AGENTS_URL}/${DELETE_ID}" | python3 -m json.tool
  exit 0
fi

if [ "${MODE}" = "adk" ]; then
  if [ -z "${REASONING_ENGINE_RESOURCE:-}" ]; then
    echo "ERROR: REASONING_ENGINE_RESOURCE is not set. Run scripts/03_deploy_adk_agent_engine.py first." >&2
    exit 1
  fi

  echo "=== Registering ADK Agent (${REASONING_ENGINE_RESOURCE}) in Gemini Enterprise App (${ENGINE_ID}) ==="
  PAYLOAD="$(python3 - "${AGENT_DISPLAY_NAME}" "${AGENT_DESCRIPTION}" "${REASONING_ENGINE_RESOURCE}" << 'EOF'
import json, sys
display_name, description, reasoning_engine = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({
    "displayName": display_name,
    "description": description,
    "adkAgentDefinition": {
        "provisionedReasoningEngine": {
            "reasoningEngine": reasoning_engine,
        }
    },
}))
EOF
)"
elif [ "${MODE}" = "a2a" ]; then
  if [ -z "${CLOUD_RUN_URL:-}" ]; then
    echo "ERROR: CLOUD_RUN_URL is not set. Run scripts/05_deploy_cloud_run.sh first." >&2
    exit 1
  fi

  echo "=== Registering A2A Agent (${CLOUD_RUN_URL}) in Gemini Enterprise App (${ENGINE_ID}) ==="
  PAYLOAD="$(python3 - "${AGENT_DISPLAY_NAME}" "${AGENT_DESCRIPTION}" "${CLOUD_RUN_URL}" << 'EOF'
import json, sys
display_name, description, service_url = sys.argv[1], sys.argv[2], sys.argv[3].rstrip("/")
agent_card = {
    "name": display_name,
    "description": description,
    "url": service_url,
    "version": "1.0.0",
    "capabilities": {"streaming": False},
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [
        {
            "id": "audit_contract",
            "name": "Audit & Redline Enterprise Contracts",
            "description": "Audits MSAs, NDAs, and LGPD DPAs against the corporate Legal Playbook with RBAC and HITL redline staging.",
            "tags": ["legal", "contracts", "lgpd", "redlining", "rbac"],
        }
    ],
}
print(json.dumps({
    "displayName": display_name,
    "description": description,
    "a2aAgentDefinition": {
        "jsonAgentCard": json.dumps(agent_card),
    },
}))
EOF
)"
else
  echo "ERROR: Invalid --mode '${MODE}'. Use 'adk' or 'a2a'." >&2
  exit 1
fi

curl -sS -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${AGENTS_URL}" \
  -d "${PAYLOAD}" | python3 -m json.tool

echo ""
echo "Done! Verify in Gemini Enterprise Console: https://console.cloud.google.com/gemini-enterprise/apps?project=${PROJECT_ID}"
