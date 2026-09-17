#!/usr/bin/env bash
# Repository credential of Argo CD (one Secret of type `repository`, exact URL).
#
#   ./scripts/credentials.sh status   what Argo CD has vs what the tree needs
#   ./scripts/credentials.sh add      create/rotate it (GIT_USER / GIT_TOKEN or gh)
#   ./scripts/credentials.sh remove   delete it (when the repository goes public)
#   ./scripts/credentials.sh admin    print the Argo CD admin password
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require kubectl
SECRET="repo-mlops-ct-platform"
case "${1:-status}" in
  status)
    step "Repository credentials in argocd"
    kubectl -n argocd get secret -l argocd.argoproj.io/secret-type=repository \
      -o custom-columns='NAME:.metadata.name,URL:.data.url' 2>/dev/null \
      | awk 'NR==1{print;next}{cmd="echo "$2" | base64 -d"; cmd | getline u; close(cmd); print $1"  "u}'
    info "tree needs: ${PLATFORM_REPO}"
    ;;
  add)
    GIT_USER="${GIT_USER:-teo-devops}"; GIT_TOKEN="${GIT_TOKEN:-$(gh auth token 2>/dev/null || true)}"
    [[ -n "$GIT_TOKEN" ]] || die "GIT_TOKEN required"
    kubectl -n argocd create secret generic "$SECRET" --from-literal=type=git --from-literal=url="$PLATFORM_REPO" \
      --from-literal=username="$GIT_USER" --from-literal=password="$GIT_TOKEN" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    kubectl -n argocd label secret "$SECRET" argocd.argoproj.io/secret-type=repository --overwrite >/dev/null
    info "credential set for ${PLATFORM_REPO}"
    ;;
  remove) kubectl -n argocd delete secret "$SECRET" --ignore-not-found ;;
  admin) kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo ;;
  *) die "unknown command: $1" ;;
esac
