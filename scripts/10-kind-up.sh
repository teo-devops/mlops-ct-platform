#!/usr/bin/env bash
# Creates the kind cluster, installs ingress-nginx and preloads the images the
# platform pulls, so that the GitOps bootstrap does not wait on the network.
# Idempotent. Pattern from teo-devops/Argo-cd-Labs lab/levantar.sh.
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require docker kind kubectl curl

INGRESS_NGINX="https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/kind/deploy.yaml"

step "kind cluster '${CLUSTER}'"
if kind get clusters 2>/dev/null | grep -qx "${CLUSTER}"; then
  info "already exists; reusing"
else
  kind create cluster --name "${CLUSTER}" --config "${REPO_ROOT}/cluster/kind.yaml"
fi
require_kind_context
kubectl wait node --all --for=condition=Ready --timeout=180s >/dev/null
info "nodes: $(kubectl get nodes --no-headers | awk '{print $1"("$2")"}' | xargs)"

step "Preloading images into the nodes"
# Everything the platform modules and the use case pull. Preloading makes the
# bootstrap deterministic and survives a flaky (or intercepted) network.
mapfile -t IMAGES < "${REPO_ROOT}/cluster/images.txt"
for img in "${IMAGES[@]}"; do
  [[ -z "$img" || "$img" == \#* ]] && continue
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    info "pulling $img"; docker pull -q "$img" >/dev/null || { echo "    ! could not pull $img (will be pulled by the node later)"; continue; }
  fi
  kind load docker-image --name "${CLUSTER}" "$img" >/dev/null 2>&1 && info "✓ $img"
done

step "ingress-nginx"
curl -fsSL "${INGRESS_NGINX}" \
  | sed -E 's|(image: registry\.k8s\.io/[^@]+)@sha256:[a-f0-9]+|\1|' \
  | kubectl apply -f - >/dev/null
kubectl -n ingress-nginx wait --for=condition=Ready pod \
  -l app.kubernetes.io/component=controller --timeout=300s >/dev/null
for _ in $(seq 1 60); do
  [[ -n "$(kubectl -n ingress-nginx get endpoints ingress-nginx-controller-admission \
             -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null)" ]] && break
  sleep 3
done
info "ready (admission webhook included); UIs will answer on http://<name>.localhost:8088"
