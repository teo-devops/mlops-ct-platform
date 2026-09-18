#!/usr/bin/env bash
# Out-of-band state of the Listing Engine use case, created BEFORE its first
# sync: its namespaces, the artifact-store credentials of its three consumers
# (minted by the platform), the Git credential of the promote step and the
# data-source ConfigMap. Run by scripts/platform/03-secrets.sh, or alone.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/scripts/lib.sh"
require kubectl
require_kind_context
UC="listing-engine"

step "${UC}: namespaces"
for ns in ${UC}-api ${UC}-serving ${UC}-pipelines; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
done
info "${UC}-{api,serving,pipelines}"

step "${UC}: artifact-store credentials (users declared in workloads/minio/values.yaml)"
minio_user_secret ${UC}-serving   models-s3-credentials   models-reader MODELS_READER
minio_user_secret ${UC}-pipelines pipeline-s3-credentials pipeline      PIPELINE
minio_user_secret ${UC}-api       api-s3-credentials      api-writer    API_WRITER

step "${UC}: Git credential for the promote step"
# Same token as the Argo CD read credential in the demo; a scoped bot token in production.
GIT_TOKEN="${GIT_TOKEN:-$(gh auth token 2>/dev/null || true)}"
GIT_USER="${GIT_USER:-teo-devops}"
if [[ -n "$GIT_TOKEN" ]]; then
  secret_upsert ${UC}-pipelines pipeline-git-credentials "GIT_USER=${GIT_USER}" "GIT_TOKEN=${GIT_TOKEN}" "GIT_REPO=${PLATFORM_REPO}"
  info "created/updated"
else
  echo "    ! no GIT_TOKEN and gh not logged in: the promote step will fail until you create it"
fi

step "${UC}: data-source state"
# Stands in for the upstream data platform: which "world" ingest sees.
# `make drift` flips it to `drift`. Not in Git on purpose.
if kubectl -n ${UC}-pipelines get configmap ct-data-source >/dev/null 2>&1; then info "kept"; else
  kubectl -n ${UC}-pipelines create configmap ct-data-source --from-literal=profile="" >/dev/null; info "created (profile: normal)"
fi
