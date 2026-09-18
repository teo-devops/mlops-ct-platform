#!/usr/bin/env bash
# Out-of-band state of the PLATFORM, created BEFORE the first sync: namespaces
# of the shared workloads and their Secrets. Never in Git (docs/design/secrets.md).
#
# The artifact-store identities (one user per consumer, declared in
# workloads/minio/values.yaml) are minted here; each use case then copies the
# keys it needs into its own namespaces with use-cases/<name>/scripts/secrets.sh,
# which this script runs last. Idempotent: existing Secrets are kept.
#
# Human-facing passwords are KNOWN DEMO DEFAULTS (README, "UIs and credentials")
# so that a fresh laptop needs no lookup; override them with the variables
# below, and rotate them before the cluster is reachable by anyone else.
# Machine-to-machine keys (artifact-store users) are always random.
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minio-demo}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin-demo}"
require kubectl python3
require_kind_context

exists() { kubectl -n "$1" get secret "$2" >/dev/null 2>&1; }

step "Platform namespaces"
for ns in minio mlflow observability; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
done
info "minio mlflow observability"

step "Artifact store: root credentials (namespace minio)"
if exists minio minio-root; then info "kept"; else
  secret_upsert minio minio-root MINIO_ROOT_USER=root "MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}"; info "created (root / \$MINIO_ROOT_PASSWORD)"
fi

step "Artifact store: one secret key per consumer user (workloads/minio/values.yaml)"
# <ENVPREFIX>_SECRET_KEY per user; existing keys are preserved, new users get one.
declare -a users_kv=()
while read -r user prefix; do
  key="$(kubectl -n minio get secret minio-users -o jsonpath="{.data.${prefix}_SECRET_KEY}" 2>/dev/null | base64 -d || true)"
  [[ -n "$key" ]] || key="$(rand_hex)"
  users_kv+=("${prefix}_SECRET_KEY=${key}")
  info "✓ user ${user} (${prefix}_SECRET_KEY)"
done < <(python3 -c '
import sys, yaml
for u in yaml.safe_load(open(sys.argv[1]))["users"]: print(u["name"], u["envPrefix"])' "${REPO_ROOT}/workloads/minio/values.yaml")
secret_upsert minio minio-users "${users_kv[@]}"

step "Registry: artifact-store credential (namespace mlflow, user mlflow)"
minio_user_secret mlflow mlflow-s3-credentials mlflow MLFLOW

step "Grafana admin (namespace observability)"
if exists observability grafana-admin; then info "kept"; else
  secret_upsert observability grafana-admin admin-user=admin "admin-password=${GRAFANA_ADMIN_PASSWORD}"; info "created (admin / \$GRAFANA_ADMIN_PASSWORD)"
fi

step "Use cases"
for uc in "${REPO_ROOT}"/use-cases/*/scripts/secrets.sh; do
  [[ -x "$uc" ]] || continue
  info "→ $(basename "$(dirname "$(dirname "$uc")")")"
  "$uc"
done

echo
echo "Demo credentials are the defaults documented in README.md (UIs and credentials); make status prints the live ones."
