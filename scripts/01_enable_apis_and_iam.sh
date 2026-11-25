#!/usr/bin/env bash
# Step 1: Enable required Google Cloud APIs and grant Discovery Engine IAM bindings
# for Gemini Enterprise App creation and Custom Agent invocation.
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "${PROJECT_ID}" ]; then
  echo "ERROR: Set GOOGLE_CLOUD_PROJECT or run 'gcloud config set project <PROJECT_ID>'." >&2
  exit 1
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
DE_SA="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com"

echo "=== [1/2] Enabling Google Cloud APIs on ${PROJECT_ID} (${PROJECT_NUMBER}) ==="
gcloud services enable \
  aiplatform.googleapis.com \
  discoveryengine.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  --project="${PROJECT_ID}"

echo "=== [2/2] Granting Discovery Engine Service Agent permissions ==="
# Ensure the Discovery Engine service identity exists before binding IAM roles.
gcloud beta services identity create \
  --service=discoveryengine.googleapis.com \
  --project="${PROJECT_ID}" >/dev/null 2>&1 || true

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="${DE_SA}" \
  --role="roles/run.invoker" \
  --condition=None >/dev/null

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="${DE_SA}" \
  --role="roles/aiplatform.user" \
  --condition=None >/dev/null

echo "Done! APIs enabled and ${DE_SA} granted roles/run.invoker + roles/aiplatform.user."
