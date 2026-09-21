#!/usr/bin/env bash
# Enable or disable a use case in the demo — its group in apps/ and projects/:
#
#   ./scripts/use-case/toggle.sh enable  <use-case>   uncomment its group lines; create its out-of-band state
#   ./scripts/use-case/toggle.sh disable <use-case>   comment them: Argo CD prunes its three workloads
#   ./scripts/use-case/toggle.sh status
#   COMMIT=1                                          also commit and push
#
# Everything about the use case stays in the repository (directory, MinIO
# buckets/users, orchestration RBAC); only whether it is DEPLOYED changes. The
# demo deploys what is listed; a laptop does not pay for use cases it is not
# looking at.
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
require python3
ACTION="${1:-status}"; UC="${2:-}"
ENV_DIR="${REPO_ROOT}/gitops/environments/demo"

status() {
  python3 - "$REPO_ROOT" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
kz = (root / "gitops/environments/demo/apps/kustomization.yaml").read_text().splitlines()
on = {m.group(1) for l in kz if (m := re.match(r"^\s*-\s*([a-z0-9-]+)\s*$", l))}
for f in sorted(root.glob("use-cases/*/usecase.yaml")):
    uc = f.parent.name
    print(f"    {uc:28s} {'on' if uc in on else 'opt-in (off)'}")
PY
}

toggle() { # <enable|disable> <uc> <file>
  python3 - "$3" "$1" "$2" <<'PY'
import pathlib, re, sys
path, action, uc = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
lines = path.read_text().splitlines()
on = re.compile(rf"^(\s*)-\s*{re.escape(uc)}\s*$"); off = re.compile(rf"^(\s*)#\s*-\s*{re.escape(uc)}\s*$")
found = False
for i, l in enumerate(lines):
    if action == "enable" and off.match(l):
        lines[i] = f"{off.match(l).group(1)}- {uc}"; found = True
    elif action == "disable" and on.match(l):
        lines[i] = f"{on.match(l).group(1)}#  - {uc}"; found = True
    elif on.match(l) or off.match(l):
        found = True
if not found:
    sys.exit(f"use case {uc!r} is not listed in {path} (make new-use-case registers it)")
path.write_text("\n".join(lines) + "\n")
PY
}

case "$ACTION" in
  status) step "Use cases in the demo (gitops/environments/demo/apps/kustomization.yaml)"; status; exit 0 ;;
  enable|disable) [[ -n "$UC" && -f "${REPO_ROOT}/use-cases/${UC}/usecase.yaml" ]] || die "usage: $0 enable|disable <use-case>  (use cases: $(ls "${REPO_ROOT}/use-cases" | grep -v README | xargs))" ;;
  *) die "unknown action: $ACTION" ;;
esac

step "${ACTION} use case ${UC}"
for f in "${ENV_DIR}/apps/kustomization.yaml" "${ENV_DIR}/projects/kustomization.yaml"; do
  toggle "$ACTION" "$UC" "$f" && info "$(realpath --relative-to="$REPO_ROOT" "$f")"
done
if [[ "$ACTION" == "enable" ]] && kubectl config current-context 2>/dev/null | grep -q "^${CTX}$"; then
  step "Out-of-band state of ${UC}"
  USE_CASE="$UC" "${REPO_ROOT}/scripts/use-case/secrets.sh" | grep -E "✓|created|kept|!" | sed 's/^/  /'
fi
step "Coherence"
python3 "${REPO_ROOT}/scripts/repo/validate-coherence.py" | tail -1
if [[ "${COMMIT:-0}" == "1" ]]; then
  git -C "${REPO_ROOT}" add "${ENV_DIR}/apps/kustomization.yaml" "${ENV_DIR}/projects/kustomization.yaml"
  git -C "${REPO_ROOT}" commit -q -m "${ACTION} use case ${UC} in the demo" && git -C "${REPO_ROOT}" push -q && info "committed and pushed: Argo CD applies it on its next poll (≤3 min)"
else
  info "now commit and push the two kustomization files (or rerun with COMMIT=1); Argo CD does the rest"
fi
