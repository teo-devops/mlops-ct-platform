#!/usr/bin/env bash
# Out-of-band state of ONE use case, created BEFORE its first sync: its
# namespaces, the artifact-store credentials of its own users (minted by the
# platform in minio/minio-users, see workloads/minio/values.yaml), the Git
# credential of the promote step and the data-source ConfigMap. Idempotent.
# scripts/platform/03-secrets.sh runs it for every use-cases/*/usecase.yaml.
. "$(dirname "${BASH_SOURCE[0]}")/lib-uc.sh"
require kubectl
require_kind_context
UC="$UC_NAME"
PREFIX="$(echo "$UC" | tr '[:lower:]-' '[:upper:]_')"

step "${UC}: namespaces"
for ns in "$UC_NS_API" "$UC_NS_SERVING" "$UC_NS_PIPELINES"; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
done
info "${UC_NS_API} ${UC_NS_SERVING} ${UC_NS_PIPELINES}"

step "${UC}: artifact-store credentials (its own users: ${UC}-reader / -pipeline / -api)"
minio_user_secret "$UC_NS_SERVING"   models-s3-credentials   "${UC}-reader"   "${PREFIX}_READER"
minio_user_secret "$UC_NS_PIPELINES" pipeline-s3-credentials "${UC}-pipeline" "${PREFIX}_PIPELINE"
minio_user_secret "$UC_NS_API"       api-s3-credentials      "${UC}-api"      "${PREFIX}_API"

step "${UC}: Git credential for the promote step"
# The promote step pushes the deployment commit; a scoped bot token in production.
GIT_TOKEN="${GIT_TOKEN:-$(gh auth token 2>/dev/null || true)}"
GIT_USER="${GIT_USER:-teo-devops}"
if [[ -n "$GIT_TOKEN" ]]; then
  secret_upsert "$UC_NS_PIPELINES" pipeline-git-credentials "GIT_USER=${GIT_USER}" "GIT_TOKEN=${GIT_TOKEN}" "GIT_REPO=${PLATFORM_REPO}"
  info "pipeline-git-credentials set (user ${GIT_USER})"
else
  echo "    ! no GIT_TOKEN and gh not logged in: the promote step will fail until you create it"
fi

step "${UC}: data-source state (ConfigMap ct-data-source)"
# "What the upstream data platform delivers now". Empty profile = normal world;
# `make drift` flips it to the use case's drift profile. Not in Git on purpose.
if kubectl -n "$UC_NS_PIPELINES" get configmap ct-data-source >/dev/null 2>&1; then info "kept"; else
  kubectl -n "$UC_NS_PIPELINES" create configmap ct-data-source --from-literal=profile= >/dev/null; info "created (profile=)"
fi
