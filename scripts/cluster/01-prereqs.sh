#!/usr/bin/env bash
# Checks the tools, the credentials and the network conditions the demo needs —
# every one of them has cost an hour of debugging in the wrong place once:
# WARP breaks TLS inside the nodes (Argo CD: x509), another kind cluster on
# :8088 makes ingress unreachable, a builder without DNS fails pip install.
#   SKIP_BUILD_CHECK=1   skip the docker-build DNS probe (slow first time)
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
ok=1
fail() { echo "    ✗ $*"; ok=0; }

step "Tools"
for t in docker kind kubectl helm python3 git gh curl; do
  if command -v "$t" >/dev/null 2>&1; then
    printf '    ✓ %-8s %s\n' "$t" "$($t --version 2>/dev/null | head -1 | cut -c1-60)"
  else
    fail "$t MISSING"
  fi
done
python3 -c 'import yaml' 2>/dev/null || fail "python3: PyYAML missing (pip install pyyaml)"
docker info >/dev/null 2>&1 || fail "docker daemon not reachable"

step "GitHub credential (the promote step pushes the deployment commit)"
if [[ -n "${GIT_TOKEN:-}" ]]; then
  info "GIT_TOKEN provided"
elif gh auth status >/dev/null 2>&1; then
  info "gh is logged in: the promote step (and a private fork's Argo CD) will use 'gh auth token'"
else
  fail "neither GIT_TOKEN nor 'gh auth login'"
fi

step "Network"
if command -v warp-cli >/dev/null 2>&1 && warp-cli status 2>/dev/null | grep -q Connected; then
  fail "Cloudflare WARP is connected: TLS is intercepted inside the kind nodes (Argo CD cannot clone GitHub: x509). Run: warp-cli disconnect"
else
  info "no TLS interception detected (WARP off or absent)"
fi
port_owner="$(docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | awk '/:8088->/ {print $1}' | head -1)"
if [[ -n "$port_owner" && "$port_owner" != "${CLUSTER}-control-plane" ]]; then
  fail "host port 8088 (the demo's ingress) is taken by container ${port_owner}; stop it or delete that kind cluster"
elif ss -ltn 2>/dev/null | grep -q ':8088 ' && [[ -z "$port_owner" ]]; then
  fail "host port 8088 (the demo's ingress) is in use by a process outside Docker"
else
  info "host port 8088 free (or already ours)"
fi
info "docker network 'kind' subnet: $(docker network inspect kind -f '{{(index .IPAM.Config 0).Subnet}}' 2>/dev/null || echo 'not created yet')"

step "Docker builder can resolve names (pip install inside the images)"
if [[ "${SKIP_BUILD_CHECK:-0}" == "1" ]]; then
  info "skipped"
else
  NETWORK_ARG=(); [[ "${DOCKER_BUILD_HOST_NETWORK:-1}" == "1" ]] && NETWORK_ARG=(--network host)
  if docker build "${NETWORK_ARG[@]}" -q -t ct-prereq-probe - >/dev/null 2>&1 <<'DOCKERFILE'; then
FROM python:3.12-slim
RUN python -c "import socket; socket.gethostbyname('pypi.org')"
DOCKERFILE
    info "ok (network: ${NETWORK_ARG[*]:-default})"; docker rmi -f ct-prereq-probe >/dev/null 2>&1 || true
  else
    fail "the builder cannot resolve pypi.org — on this laptop set DOCKER_BUILD_HOST_NETWORK=1 (default) or fix Docker's DNS"
  fi
fi

step "Resources"
avail_gb="$(awk '/MemAvailable/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)"
if [[ "$avail_gb" -lt 8 ]]; then
  fail "only ${avail_gb} GiB available: the demo needs ~8 GiB (core) — free memory or stop other clusters"
else
  info "${avail_gb} GiB available"
fi
cpus="$(nproc 2>/dev/null || echo 1)"; [[ "$cpus" -ge 4 ]] && info "${cpus} CPUs" || fail "${cpus} CPUs: 4 recommended"

step "What the demo will deploy"
"${REPO_ROOT}/scripts/platform/module.sh" status | sed -n '2,$p'
"${REPO_ROOT}/scripts/use-case/toggle.sh" status | sed -n '2,$p'

[[ $ok -eq 1 ]] && echo -e "\nAll prerequisites satisfied." || die "fix the items marked ✗"
