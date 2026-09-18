#!/usr/bin/env bash
# Shared helpers for the scripts. Source it from a script in a subfolder:
#   . "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="${CLUSTER:-ct}"
CTX="kind-${CLUSTER}"
PLATFORM_REPO="https://github.com/teo-devops/mlops-ct-platform.git"

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die()  { printf '\033[31mABORTED: %s\033[0m\n' "$*" >&2; exit 1; }

require() {
  local missing=0
  for t in "$@"; do
    command -v "$t" >/dev/null 2>&1 || { echo "missing tool: $t" >&2; missing=1; }
  done
  [[ $missing -eq 0 ]] || die "install the missing tools first (scripts/cluster/01-prereqs.sh)"
}

# Refuse to touch any cluster that is not the kind cluster of this repo.
require_kind_context() {
  local current
  current="$(kubectl config current-context 2>/dev/null || true)"
  [[ "${current}" == "${CTX}" ]] || die "kubectl context is '${current}', expected '${CTX}' (run make up)"
}

# kubectl apply with retries: CRDs and webhooks take a moment to be ready.
apply_retry() {
  local i
  for i in $(seq 1 40); do
    kubectl apply -f "$1" >/dev/null 2>&1 && return 0
    sleep 3
  done
  kubectl apply -f "$1"
}

# Idempotent Secret creation from literals: `secret_upsert ns name k=v k=v...`
secret_upsert() {
  local ns="$1" name="$2"; shift 2
  local args=()
  for kv in "$@"; do args+=(--from-literal="$kv"); done
  kubectl -n "$ns" create secret generic "$name" "${args[@]}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
}

wait_apps_healthy() {   # wait_apps_healthy <timeout-seconds> [app-name-regex]
  local timeout="$1" filter="${2:-.*}" deadline now
  deadline=$(( $(date +%s) + timeout ))
  while true; do
    local pending
    pending="$(kubectl -n argocd get applications -o json 2>/dev/null \
      | python3 -c '
import json,sys,re
flt=re.compile(sys.argv[1])
apps=json.load(sys.stdin)["items"]
bad=[]
for a in apps:
    n=a["metadata"]["name"]
    if not flt.fullmatch(n): continue
    h=a.get("status",{}).get("health",{}).get("status","Unknown")
    s=a.get("status",{}).get("sync",{}).get("status","Unknown")
    if h!="Healthy" or s!="Synced": bad.append(f"{n}({s}/{h})")
print(" ".join(bad))' "$filter")"
    [[ -z "$pending" ]] && return 0
    now=$(date +%s)
    [[ $now -lt $deadline ]] || { echo "timed out waiting for: $pending" >&2; return 1; }
    printf '    waiting: %s\n' "$pending"
    sleep 15
  done
}
