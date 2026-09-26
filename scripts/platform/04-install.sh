#!/usr/bin/env bash
#
# Bootstrap of the GitOps engine on a cluster from scratch.
#
# The only imperative procedure of the project, run ONCE in the life of the
# cluster. From phase 3 on, every change is a commit on main.
#
#   Usage:  ./scripts/platform/04-install.sh                 bootstrap (phases 0-3)
#           ./scripts/platform/04-install.sh credential status|add|remove
#                                            the Argo CD repository credential alone
#                                            (a PRIVATE fork needs one; the public
#                                            repository is cloned anonymously)
#           ./scripts/platform/04-install.sh admin-password
#   Env:    GIT_USER / GIT_TOKEN  read credential of a private fork
#           (defaults: teo-devops / `gh auth token`; GIT_TOKEN= skips it)
#           ASSUME_YES=1          do not ask for confirmation
#
# Idempotent. Inherited from teo-devops/Argo-cd-Labs scripts/install.sh.
#
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
require kubectl helm

CHART_VERSION="10.2.2"   # -> Argo CD v3.4.6. Must match gitops/environments/demo/argo-cd.yaml
NAMESPACE="argocd"
PLATFORM_SECRET="repo-mlops-ct-platform"

credential_add() {
  GIT_USER="${GIT_USER:-teo-devops}"; GIT_TOKEN="${GIT_TOKEN-$(gh auth token 2>/dev/null || true)}"
  [[ -n "$GIT_TOKEN" ]] || die "GIT_TOKEN required (or 'gh auth login')"
  kubectl -n "${NAMESPACE}" create secret generic "${PLATFORM_SECRET}" \
    --from-literal=type=git --from-literal=url="${PLATFORM_REPO}" \
    --from-literal=username="${GIT_USER}" --from-literal=password="${GIT_TOKEN}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  kubectl -n "${NAMESPACE}" label secret "${PLATFORM_SECRET}" \
    argocd.argoproj.io/secret-type=repository --overwrite >/dev/null
  info "credential installed for ${PLATFORM_REPO}"
}

case "${1:-}" in
  credential)
    case "${2:-status}" in
      status)
        step "Repository credentials in ${NAMESPACE}"
        kubectl -n "${NAMESPACE}" get secret -l argocd.argoproj.io/secret-type=repository \
          -o custom-columns='NAME:.metadata.name,URL:.data.url' 2>/dev/null \
          | awk 'NR==1{print;next}{cmd="echo "$2" | base64 -d"; cmd | getline u; close(cmd); print $1"  "u}'
        info "tree needs: ${PLATFORM_REPO}" ;;
      add) credential_add ;;
      remove) kubectl -n "${NAMESPACE}" delete secret "${PLATFORM_SECRET}" --ignore-not-found ;;
      *) die "usage: $0 credential status|add|remove" ;;
    esac
    exit 0 ;;
  admin-password)
    # The bcrypt in gitops/argo-cd/values.yaml wins (README: admin-demo); the initial secret only
    # exists before it applies.
    kubectl -n "${NAMESPACE}" get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null | base64 -d \
      || echo "admin-demo (gitops/argo-cd/values.yaml)"; echo; exit 0 ;;
  "") ;;
  *) die "unknown command: $1" ;;
esac

echo "==> kubectl context: $(kubectl config current-context)"
if [[ "${ASSUME_YES:-0}" != "1" ]]; then
  read -rp "    Continue on this cluster? [y/N] " ok
  [[ "$ok" == "y" || "$ok" == "Y" ]] || die "cancelled"
fi

# --- Phase 0: namespace and the credential of the platform repository ------
# The repository is public: Argo CD clones it anonymously and this Secret is
# optional. A private fork needs it, and it cannot be in Git (Argo CD needs it
# to clone the repo that would contain it): without it root-app sits at
# `sync: Unknown` with `health: Healthy` — the failure that goes unnoticed if
# you only look at that column. Set GIT_TOKEN= (empty) to skip it explicitly.
step "Phase 0: namespace and platform repository credential"
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
GIT_USER="${GIT_USER:-teo-devops}"
GIT_TOKEN="${GIT_TOKEN-$(gh auth token 2>/dev/null || true)}"
if kubectl -n "${NAMESPACE}" get secret "${PLATFORM_SECRET}" >/dev/null 2>&1 && [[ -z "${GIT_TOKEN}" ]]; then
  info "Secret ${PLATFORM_SECRET} exists and no GIT_TOKEN given: kept"
elif [[ -z "${GIT_TOKEN}" ]]; then
  info "no GIT_TOKEN: no repository credential (fine for the public repository; a private fork needs one)"
else
  # A rejected token is worse than none: Argo CD sends it and GitHub refuses the
  # clone even of the public repository (`gh auth token` still prints an expired one).
  curl -fsS -o /dev/null -H @- https://api.github.com/user <<<"Authorization: token ${GIT_TOKEN}" 2>/dev/null \
    || die "GitHub rejects the token (expired? run 'gh auth login', or GIT_TOKEN= to skip the credential)"
  credential_add
fi

# --- Phase 1: Argo CD from the official chart, rendered with the SAME values
# file that Argo CD will later use to manage itself.
step "Phase 1: installing Argo CD chart ${CHART_VERSION}"
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo update argo >/dev/null
helm template argo-cd argo/argo-cd \
  --version "${CHART_VERSION}" \
  --namespace "${NAMESPACE}" \
  --include-crds \
  --values "${REPO_ROOT}/gitops/argo-cd/values.yaml" \
  | kubectl apply --server-side --force-conflicts -f - >/dev/null
info "applied"

# --- Phase 2: wait for the CRDs, then for the repo-server ------------------
step "Phase 2: waiting for CRDs and repo-server"
kubectl wait --for=condition=Established --timeout=120s \
  crd/applications.argoproj.io crd/appprojects.argoproj.io crd/applicationsets.argoproj.io >/dev/null
kubectl -n "${NAMESPACE}" rollout status deploy/argocd-repo-server --timeout=300s >/dev/null
kubectl -n "${NAMESPACE}" rollout status deploy/argocd-server --timeout=300s >/dev/null
info "ready"

# --- Phase 3: AppProjects and root-app -------------------------------------
step "Phase 3: applying AppProjects and root-app"
kubectl apply -k "${REPO_ROOT}/gitops/bootstrap" >/dev/null
info "root-app applied; everything else arrives by reconciliation"

cat <<EOT

==> GitOps engine started. From here on no command is run against the
    control plane: every change is a commit on main.

    UI:        http://argocd.localhost:8088   (user admin)
    Password:  kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
    Status:    kubectl -n argocd get applications
EOT
