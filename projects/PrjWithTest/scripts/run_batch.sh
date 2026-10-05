#!/usr/bin/env bash
# Ejecuta el Job de Cloud Run del lote reanudable (requiere haber corrido
# scripts/deploy.sh antes). Reanudable: volver a ejecutar este script no
# duplica resenas ya procesadas (ver vendebot/batch/runner.py).

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Define PROJECT_ID}"
REGION="${REGION:-us-central1}"
JOB_NAME="${JOB_NAME:-vendebot-batch}"

gcloud config set project "${PROJECT_ID}"
gcloud run jobs execute "${JOB_NAME}" --region="${REGION}" --wait
