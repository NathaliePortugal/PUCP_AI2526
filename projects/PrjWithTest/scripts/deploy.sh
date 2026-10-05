#!/usr/bin/env bash
# Despliegue parametrizado en GCP: habilita APIs, crea Artifact Registry,
# Secret Manager, Firestore, el servicio de Cloud Run (API) y el Job de
# Cloud Run (lote). Pensado para correrse tanto desde una cuenta propia como
# desde un entorno provisto por el docente: todo se configura por variables
# de entorno, nada queda hardcodeado.
#
# Uso:
#   export PROJECT_ID=mi-proyecto
#   export GEMINI_API_KEY=xxxx
#   ./scripts/deploy.sh
#
# Requisitos previos: gcloud autenticado (gcloud auth login) y con el
# proyecto facturable habilitado. Docker corriendo localmente.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Define PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-vendebot-api}"
JOB_NAME="${JOB_NAME:-vendebot-batch}"
REPO_NAME="${REPO_NAME:-vendebot}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/vendebot:${IMAGE_TAG}"

GEMINI_API_KEY="${GEMINI_API_KEY:?Define GEMINI_API_KEY}"
LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-}"
LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-}"
LANGFUSE_HOST="${LANGFUSE_HOST:-https://cloud.langfuse.com}"

echo "== Proyecto: ${PROJECT_ID} | region: ${REGION} =="
gcloud config set project "${PROJECT_ID}"

echo "== Habilitando APIs =="
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com

echo "== Artifact Registry =="
gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker --location="${REGION}" \
    --description="Imagenes de VendeBot"

echo "== Firestore (modo nativo) =="
gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 || \
  gcloud firestore databases create --location="${REGION}" --type=firestore-native

echo "== Secret Manager =="
create_or_update_secret() {
  local name="$1" value="$2"
  [ -z "$value" ] && return 0
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=-
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=-
  fi
}
create_or_update_secret vendebot-gemini-api-key "${GEMINI_API_KEY}"
create_or_update_secret vendebot-langfuse-public-key "${LANGFUSE_PUBLIC_KEY}"
create_or_update_secret vendebot-langfuse-secret-key "${LANGFUSE_SECRET_KEY}"

echo "== Build y push de la imagen =="
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build -t "${IMAGE}" .
docker push "${IMAGE}"

SECRETS_FLAGS="GEMINI_API_KEY=vendebot-gemini-api-key:latest"
[ -n "${LANGFUSE_PUBLIC_KEY}" ] && SECRETS_FLAGS="${SECRETS_FLAGS},LANGFUSE_PUBLIC_KEY=vendebot-langfuse-public-key:latest"
[ -n "${LANGFUSE_SECRET_KEY}" ] && SECRETS_FLAGS="${SECRETS_FLAGS},LANGFUSE_SECRET_KEY=vendebot-langfuse-secret-key:latest"

ENV_FLAGS="STORAGE_BACKEND=firestore,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},LANGFUSE_HOST=${LANGFUSE_HOST}"

echo "== Desplegando el servicio (API) en Cloud Run =="
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=3 \
  --set-env-vars="${ENV_FLAGS}" \
  --set-secrets="${SECRETS_FLAGS}"

echo "== Creando/actualizando el Job (lote) en Cloud Run =="
if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" >/dev/null 2>&1; then
  gcloud run jobs update "${JOB_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --command="python" \
    --args="-m,vendebot.batch" \
    --set-env-vars="${ENV_FLAGS}" \
    --set-secrets="${SECRETS_FLAGS}"
else
  gcloud run jobs create "${JOB_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --command="python" \
    --args="-m,vendebot.batch" \
    --set-env-vars="${ENV_FLAGS}" \
    --set-secrets="${SECRETS_FLAGS}"
fi

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)')
echo ""
echo "== Listo =="
echo "Servicio: ${SERVICE_URL}"
echo "Probar:   curl ${SERVICE_URL}/health"
echo "Lote:     ./scripts/run_batch.sh"
