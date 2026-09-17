#!/usr/bin/env bash
# Checks the tools and the network conditions the demo needs.
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

step "Tools"
ok=1
for t in docker kind kubectl helm python3 git gh curl; do
  if command -v "$t" >/dev/null 2>&1; then
    printf '    ✓ %-8s %s\n' "$t" "$($t --version 2>/dev/null | head -1 | cut -c1-60)"
  else
    printf '    ✗ %-8s MISSING\n' "$t"; ok=0
  fi
done
python3 -c 'import yaml' 2>/dev/null || { echo "    ✗ python3: PyYAML missing (pip install pyyaml)"; ok=0; }
docker info >/dev/null 2>&1 || { echo "    ✗ docker daemon not reachable"; ok=0; }

step "GitHub credential (Argo CD reads a private repository)"
if [[ -n "${GIT_TOKEN:-}" ]]; then
  info "GIT_TOKEN provided"
elif gh auth status >/dev/null 2>&1; then
  info "gh is logged in: install.sh will use 'gh auth token'"
else
  echo "    ✗ neither GIT_TOKEN nor 'gh auth login'"; ok=0
fi

step "Network"
if command -v warp-cli >/dev/null 2>&1 && warp-cli status 2>/dev/null | grep -q Connected; then
  echo "    ! Cloudflare WARP is connected: TLS is intercepted and image pulls inside kind nodes will fail (x509). Disconnect it first."
fi
info "docker network 'kind' subnet: $(docker network inspect kind -f '{{(index .IPAM.Config 0).Subnet}}' 2>/dev/null || echo 'not created yet')"

[[ $ok -eq 1 ]] && echo -e "\nAll prerequisites satisfied." || die "fix the items marked ✗"
