#!/usr/bin/env bash
# Renders what Argo CD would apply: the control-plane tree (Kustomize) and the
# engine chart with its values. The PR shows Kustomize and chart versions, not
# the objects that end up in the apiserver — this is the "rendered manifests"
# pattern by hand. CI publishes the diff.
#
#   Usage:  ./scripts/render.sh <output-dir>
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
OUT="${1:?usage: $0 <output-dir>}"
mkdir -p "${OUT}"
kubectl kustomize "${REPO_ROOT}/overlays/demo" > "${OUT}/01-control-plane.yaml"
kubectl kustomize "${REPO_ROOT}/bootstrap" > "${OUT}/00-bootstrap.yaml"
CHART_VERSION="$(awk '/chart: argo-cd/ {f=1} f && /targetRevision:/ {print $2; exit}' "${REPO_ROOT}/overlays/demo/argo-cd.yaml")"
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo update argo >/dev/null 2>&1
helm template argo-cd argo/argo-cd --version "${CHART_VERSION}" --namespace argocd --include-crds \
  --values "${REPO_ROOT}/config/argo-cd/values.yaml" > "${OUT}/02-engine-argocd.yaml"
for chart in "${REPO_ROOT}"/workloads/*/ "${REPO_ROOT}"/use-cases/*/workloads/*/; do
  [[ -f "${chart}/Chart.yaml" ]] || continue
  name="$(basename "$(dirname "${chart}")")-$(basename "${chart}")"
  helm template "$(basename "${chart}")" "${chart}" -f "${chart}/values.yaml" -f "${chart}/values-demo.yaml" \
    > "${OUT}/10-workload-${name}.yaml"
done
echo "==> rendered in ${OUT}"; wc -l "${OUT}"/*.yaml
