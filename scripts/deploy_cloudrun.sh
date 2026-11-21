#!/usr/bin/env bash
set -euo pipefail

# Deploy pubblico HTTPS su Google Cloud Run con 1 comando (MedioMeteo Genova v4.0)
# Uso:
#   ./scripts/deploy_cloudrun.sh [GCP_PROJECT_ID] [REGION] [SERVICE_NAME]
# Variabile opzionale per Gemini AI live: GEMINI_API_KEY

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${2:-europe-west8}"
SERVICE_NAME="${3:-mediometeo-genova}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Errore: specifica il GCP Project ID: ./scripts/deploy_cloudrun.sh <PROJECT_ID>" >&2
  exit 1
fi

echo "1. Pre-release check sicurezza & ADR..."
PRE_RELEASE_SCRIPT="${HOME}/.gemini/config/skills/adr-github-methodology/scripts/pre_release_check.py"
if [[ -f "${PRE_RELEASE_SCRIPT}" ]]; then
  python3 "${PRE_RELEASE_SCRIPT}"
else
  echo "   [skip] pre_release_check.py non presente in questo ambiente."
fi

echo "2. Esecuzione suite offline deterministica..."
.venv/bin/pytest -q -m "not live"

ENV_VARS="MEDIOMETEO_DB_PATH=/tmp/mediometeo.sqlite,TRUST_PROXY_HEADERS=true"
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
fi

echo "3. Deploy Cloud Run su ${PROJECT_ID} (${REGION}) -> ${SERVICE_NAME}..."
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --memory 512Mi \
  --set-env-vars "${ENV_VARS}"
