#!/usr/bin/env bash
# Step 5 (Cloud Run Option): Deploy the FastAPI Legal & Contract Redlining Agent
# (with Web UI, OpenAPI 3.0 spec, and /.well-known/agent.json A2A card) to Cloud Run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "${PROJECT_ID}" ]; then
  echo "ERROR: Set GOOGLE_CLOUD_PROJECT or run 'gcloud config set project <PROJECT_ID>'." >&2
  exit 1
fi

REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-gemini-enterprise-legal-agent}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3-flash-preview}"

echo "=== Deploying ${SERVICE_NAME} to Cloud Run (${PROJECT_ID} / ${REGION}) ==="
gcloud run deploy "${SERVICE_NAME}" \
  --source "${ROOT_DIR}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=${GEMINI_MODEL}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format='value(status.url)')"

echo "CLOUD_RUN_URL=${SERVICE_URL}" >> "${ROOT_DIR}/.ge_env"
echo ""
echo "Deployed! Live URL: ${SERVICE_URL}"
echo "  OpenAPI 3.0 Spec:  ${SERVICE_URL}/openapi.json"
echo "  A2A Agent Card:    ${SERVICE_URL}/.well-known/agent.json"
echo "Next step: ./scripts/04_register_agent_in_ge.sh --mode a2a"
