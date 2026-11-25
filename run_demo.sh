#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

export GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI:-true}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3-flash-preview}"
PORT="${PORT:-8081}"

echo "Starting Gemini Enterprise Legal & Contract Redlining Agent on http://0.0.0.0:${PORT}"
echo "  OpenAPI 3.0 Connector Spec: http://0.0.0.0:${PORT}/openapi.json"
echo "  GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT:-<not set>}"

exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
