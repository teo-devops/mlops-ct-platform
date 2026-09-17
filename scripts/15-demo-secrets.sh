#!/usr/bin/env bash
# Creates the namespaces and the Secrets of the demo BEFORE the first sync.
#
# Secrets are never declared in Git (docs/secrets.md). Two things force this
# order: the MinIO provisioning Job needs the user secret keys the moment it
# runs, and the InferenceServices need their S3 credentials on the first
# attempt. Idempotent: existing Secrets are kept (rotation = delete + rerun).
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require kubectl
require_kind_context

rand() { openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

exists() { kubectl -n "$1" get secret "$2" >/dev/null 2>&1; }

step "Namespaces"
for ns in minio mlflow observability listing-engine-api listing-engine-serving listing-engine-pipelines; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
done
info "minio mlflow observability listing-engine-{api,serving,pipelines}"

step "MinIO root credentials (namespace minio)"
if exists minio minio-root; then info "kept"; else
  secret_upsert minio minio-root MINIO_ROOT_USER=root "MINIO_ROOT_PASSWORD=$(rand)"; info "created"
fi

step "MinIO consumer users — one secret key per user, delivered to each consumer namespace"
# user  env-prefix  consumer-namespace  consumer-secret-name
USERS=(
  "mlflow        MLFLOW        mlflow                   mlflow-s3-credentials"
  "models-reader MODELS_READER listing-engine-serving   models-s3-credentials"
  "pipeline      PIPELINE      listing-engine-pipelines pipeline-s3-credentials"
  "api-writer    API_WRITER    listing-engine-api       api-s3-credentials"
)
if exists minio minio-users; then
  info "minio/minio-users kept; consumer secrets re-derived from it"
fi
declare -a users_kv=()
for entry in "${USERS[@]}"; do
  read -r user prefix ns secret <<<"$entry"
  key="$(kubectl -n minio get secret minio-users -o jsonpath="{.data.${prefix}_SECRET_KEY}" 2>/dev/null | base64 -d || true)"
  [[ -n "$key" ]] || key="$(rand)"
  users_kv+=("${prefix}_SECRET_KEY=${key}")
  secret_upsert "$ns" "$secret" "AWS_ACCESS_KEY_ID=${user}" "AWS_SECRET_ACCESS_KEY=${key}"
  info "✓ ${ns}/${secret} (user ${user})"
done
secret_upsert minio minio-users "${users_kv[@]}"

step "Grafana admin (namespace observability)"
if exists observability grafana-admin; then info "kept"; else
  secret_upsert observability grafana-admin admin-user=admin "admin-password=$(rand)"; info "created"
fi

step "Git credential for the promote step (namespace listing-engine-pipelines)"
# The pipeline commits the model version bump. Same token as the Argo CD
# read credential in the demo; a dedicated bot token in production.
GIT_TOKEN="${GIT_TOKEN:-$(gh auth token 2>/dev/null || true)}"
GIT_USER="${GIT_USER:-teo-devops}"
if [[ -n "$GIT_TOKEN" ]]; then
  secret_upsert listing-engine-pipelines pipeline-git-credentials "GIT_USER=${GIT_USER}" "GIT_TOKEN=${GIT_TOKEN}" "GIT_REPO=${PLATFORM_REPO}"
  info "created/updated"
else
  echo "    ! no GIT_TOKEN and gh not logged in: the promote step will fail until you create it"
fi

echo
echo "Passwords live only in the cluster. Read them with: make status"
