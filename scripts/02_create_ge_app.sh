#!/usr/bin/env bash
# Step 2: Spin up a Gemini Enterprise Data Store (seeded with synthetic Legal Playbook
# docs in GCS) and create a Gemini Enterprise App (Engine with APP_TYPE_INTRANET).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "${PROJECT_ID}" ]; then
  echo "ERROR: Set GOOGLE_CLOUD_PROJECT or run 'gcloud config set project <PROJECT_ID>'." >&2
  exit 1
fi

GE_LOCATION="${GE_LOCATION:-global}"
ENGINE_ID="${GE_ENGINE_ID:-legal-redline-ge-app}"
ENGINE_DISPLAY_NAME="${GE_ENGINE_DISPLAY_NAME:-Legal & Contract Redlining GE App}"
DATA_STORE_ID="${GE_DATA_STORE_ID:-legal-playbook-ds}"
COMPANY_NAME="${GE_COMPANY_NAME:-Enterprise Legal Ops}"
GCS_BUCKET="${GE_GCS_BUCKET:-${PROJECT_ID}-ge-legal-playbook}"
GCS_REGION="${GCS_REGION:-us-central1}"

if [ "${GE_LOCATION}" = "global" ]; then
  DE_HOST="discoveryengine.googleapis.com"
else
  DE_HOST="${GE_LOCATION}-discoveryengine.googleapis.com"
fi

ACCESS_TOKEN="$(gcloud auth print-access-token)"

echo "=== [1/4] Creating GCS bucket gs://${GCS_BUCKET} and uploading synthetic playbook docs ==="
gcloud storage buckets create "gs://${GCS_BUCKET}" \
  --project="${PROJECT_ID}" \
  --location="${GCS_REGION}" \
  --uniform-bucket-level-access >/dev/null 2>&1 || echo "Bucket gs://${GCS_BUCKET} already exists."

TMP_DOCS="$(mktemp -d)"
trap 'rm -rf "${TMP_DOCS}"' EXIT

python3 - "${ROOT_DIR}" "${TMP_DOCS}" << 'EOF'
import sys
from pathlib import Path

root_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(root_dir))
from app.playbook import LEGAL_PLAYBOOK

for rule in LEGAL_PLAYBOOK:
    # Only upload standard non-restricted playbook rules to the general GCS data store.
    if "sales_rep" not in rule["allowed_roles"]:
        continue
    content = (
        f"# {rule['rule_id']}: {rule['title']}\n\n"
        f"Category: {rule['category']}\n\n"
        f"## Standard Position\n{rule['standard_position']}\n\n"
        f"## Fallback Position\n{rule['fallback_position']}\n\n"
        f"## Approved Redline Template\n{rule['redline_template']}\n"
    )
    (out_dir / f"{rule['rule_id'].lower()}.txt").write_text(content, encoding="utf-8")
print("Exported synthetic playbook documents.")
EOF

gcloud storage cp "${TMP_DOCS}"/*.txt "gs://${GCS_BUCKET}/playbook/" --quiet

echo "=== [2/4] Creating Gemini Enterprise Data Store (${DATA_STORE_ID}) ==="
curl -sS -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://${DE_HOST}/v1/projects/${PROJECT_ID}/locations/${GE_LOCATION}/collections/default_collection/dataStores?dataStoreId=${DATA_STORE_ID}" \
  -d "{
    \"displayName\": \"Corporate Legal Redline Playbook\",
    \"industryVertical\": \"GENERIC\",
    \"solutionTypes\": [\"SOLUTION_TYPE_SEARCH\"],
    \"contentConfig\": \"CONTENT_REQUIRED\"
  }" | python3 -m json.tool || true

echo "=== [3/4] Importing Legal Playbook documents from GCS into Data Store ==="
curl -sS -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://${DE_HOST}/v1/projects/${PROJECT_ID}/locations/${GE_LOCATION}/collections/default_collection/dataStores/${DATA_STORE_ID}/branches/default_branch/documents:import" \
  -d "{
    \"gcsSource\": {
      \"inputUris\": [\"gs://${GCS_BUCKET}/playbook/*.txt\"],
      \"dataSchema\": \"content\"
    },
    \"reconciliationMode\": \"INCREMENTAL\"
  }" | python3 -m json.tool || true

echo "=== [4/4] Creating Gemini Enterprise App / Engine (${ENGINE_ID}) ==="
curl -sS -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://${DE_HOST}/v1/projects/${PROJECT_ID}/locations/${GE_LOCATION}/collections/default_collection/engines?engineId=${ENGINE_ID}" \
  -d "{
    \"displayName\": \"${ENGINE_DISPLAY_NAME}\",
    \"dataStoreIds\": [\"${DATA_STORE_ID}\"],
    \"solutionType\": \"SOLUTION_TYPE_SEARCH\",
    \"industryVertical\": \"GENERIC\",
    \"appType\": \"APP_TYPE_INTRANET\",
    \"commonConfig\": {
      \"companyName\": \"${COMPANY_NAME}\"
    }
  }" | python3 -m json.tool

cat > "${ROOT_DIR}/.ge_env" << ENVEOF
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GE_LOCATION=${GE_LOCATION}
GE_ENGINE_ID=${ENGINE_ID}
GE_DATA_STORE_ID=${DATA_STORE_ID}
GE_GCS_BUCKET=${GCS_BUCKET}
ENVEOF

echo ""
echo "Saved GE configuration to ${ROOT_DIR}/.ge_env"
echo "Open Gemini Enterprise Apps Console: https://console.cloud.google.com/gemini-enterprise/apps?project=${PROJECT_ID}"
