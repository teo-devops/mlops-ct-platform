#!/usr/bin/env bash
# The development loop: the SAME charts and values as gitops/environments/demo, applied
# with helm/kubectl directly from the working tree — no commit, no Argo CD.
# Use it to iterate on a chart before pushing; `make bootstrap` is the real
# path. Order = the sync-waves of gitops/environments/demo/platform/kustomization.yaml.
#
#   ./scripts/platform/deploy-local.sh            # everything
#   ./scripts/platform/deploy-local.sh use-cases  # only the use-case workloads
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
require helm kubectl
require_kind_context
P="${REPO_ROOT}/gitops/environments/demo/platform"
SCOPE="${1:-all}"

# chart_version <module>  -> targetRevision of the module's Application
chart_version() { awk '/^    - repoURL:/ {f=1} f && /targetRevision:/ {print $2; exit}' "$P/$1/application.yaml"; }
# Helm cannot adopt objects that Argo CD created: run this on a cluster WITHOUT
# the GitOps engine (make up + make secrets, skip make bootstrap). DRY_RUN=1
# only renders and validates the manifests against the API server.
hi() { local rel="$1" ns="$2" chart="$3" ver="$4"; shift 4
       local vflag=(); [[ -n "$ver" ]] && vflag=(--version "$ver")
       if [[ "${DRY_RUN:-0}" == "1" ]]; then
         helm template "$rel" "$chart" "${vflag[@]}" -n "$ns" "$@" | kubectl apply --server-side --force-conflicts --dry-run=server -f - >/dev/null && info "✓ $rel renders and validates ($chart ${ver:-local})"
       else
         helm upgrade --install "$rel" "$chart" "${vflag[@]}" -n "$ns" --create-namespace --wait --timeout 10m "$@" >/dev/null && info "✓ $rel ($chart ${ver:-local})"
       fi; }

if [[ "$SCOPE" == "all" ]]; then
  step "Platform modules (helm, same values as gitops/environments/demo/platform)"
  for r in argo jetstack prometheus-community community-charts; do helm repo add "$r" \
    "$( [[ $r == argo ]] && echo https://argoproj.github.io/argo-helm || [[ $r == jetstack ]] && echo https://charts.jetstack.io || [[ $r == prometheus-community ]] && echo https://prometheus-community.github.io/helm-charts || echo https://community-charts.github.io/helm-charts )" >/dev/null 2>&1 || true; done
  helm repo update >/dev/null
  hi cert-manager cert-manager jetstack/cert-manager "$(chart_version cert-manager)" -f "$P/cert-manager/values.yaml"
  [[ "${DRY_RUN:-0}" == "1" ]] || kubectl apply --server-side -k "https://github.com/kubernetes-sigs/gateway-api/config/crd/standard?ref=v1.5.1" >/dev/null && info "✓ gateway-api-crds"
  hi kserve-crd kserve oci://ghcr.io/kserve/charts/kserve-crd "$(chart_version kserve-crd)"
  kubectl apply -f "$P/mlflow/manifests" ${DRY_RUN:+--dry-run=server} >/dev/null
  hi mlflow mlflow community-charts/mlflow "$(chart_version mlflow)" -f "$P/mlflow/values.yaml"
  kubectl apply -f "$P/argo-workflows/manifests" ${DRY_RUN:+--dry-run=server} >/dev/null
  hi argo-workflows argo argo/argo-workflows "$(chart_version argo-workflows)" -f "$P/argo-workflows/values.yaml"
  hi kps observability prometheus-community/kube-prometheus-stack "$(chart_version kube-prometheus-stack)" -f "$P/kube-prometheus-stack/values.yaml"
  hi pushgateway observability prometheus-community/prometheus-pushgateway "$(chart_version pushgateway)" -f "$P/pushgateway/values.yaml"
  hi kserve kserve oci://ghcr.io/kserve/charts/kserve-resources "$(chart_version kserve)" -f "$P/kserve/values.yaml"
  hi kserve-runtimes kserve oci://ghcr.io/kserve/charts/kserve-runtime-configs "$(chart_version kserve-runtimes)" -f "$P/kserve-runtimes/values.yaml"

  step "Shared workloads"
  hi minio minio "${REPO_ROOT}/workloads/minio" "" -f "${REPO_ROOT}/workloads/minio/values.yaml" -f "${REPO_ROOT}/workloads/minio/values-demo.yaml"
  hi observability observability "${REPO_ROOT}/workloads/observability" "" -f "${REPO_ROOT}/workloads/observability/values.yaml" -f "${REPO_ROOT}/workloads/observability/values-demo.yaml"
fi

step "Use-case workloads (every use-cases/*/workloads/* chart)"
for chart in "${REPO_ROOT}"/use-cases/*/workloads/*/; do
  [[ -f "${chart}/Chart.yaml" ]] || continue
  uc="$(basename "$(dirname "$(dirname "${chart}")")")"; w="$(basename "${chart}")"
  hi "${uc}-${w}" "${uc}-${w}" "${chart}" "" -f "${chart}/values.yaml" -f "${chart}/values-demo.yaml"
done
info "done — remember: nothing here is in Git until you commit it"
