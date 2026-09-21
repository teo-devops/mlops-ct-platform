#!/usr/bin/env bash
# Enable or disable an OPT-IN platform module in the demo — everything the
# module's card used to ask by hand, in one command:
#
#   ./scripts/platform/module.sh enable  <module>     uncomment its line in the platform kustomization,
#                                                     preload its images, create its out-of-band state
#   ./scripts/platform/module.sh disable <module>     comment the line, run the module's disable hook
#   ./scripts/platform/module.sh status               what is on, what is opt-in
#   COMMIT=1                                          also commit and push (Argo CD acts on main)
#
# A module may ship hooks in gitops/environments/demo/platform/<module>/hooks/
# {enable,disable}.sh for what neither the chart nor the secrets script cover
# (e.g. argo-rollouts leaves a selector on Services when it goes).
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
require python3
ACTION="${1:-status}"; MODULE="${2:-}"
PLATFORM="${REPO_ROOT}/gitops/environments/demo/platform"

list_modules() {
  python3 - "$PLATFORM_KUSTOMIZATION" "$PLATFORM" <<'PY'
import pathlib, re, sys
kz = pathlib.Path(sys.argv[1]).read_text().splitlines()
on = {m.group(1) for l in kz if (m := re.match(r"^\s*-\s*([a-z0-9-]+)\s*$", l))}
optin = {m.group(1) for l in kz if (m := re.match(r"^\s*#\s*-\s*([a-z0-9-]+)\s*$", l))}
for d in sorted(p.name for p in pathlib.Path(sys.argv[2]).iterdir() if p.is_dir()):
    state = "on" if d in on else "opt-in (off)" if d in optin else "NOT LISTED"
    print(f"    {d:24s} {state}")
PY
}

toggle() { # <enable|disable> <module>
  python3 - "$PLATFORM_KUSTOMIZATION" "$1" "$2" <<'PY'
import pathlib, re, sys
path, action, mod = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
lines = path.read_text().splitlines()
on = re.compile(rf"^(\s*)-\s*{re.escape(mod)}\s*$"); off = re.compile(rf"^(\s*)#\s*-\s*{re.escape(mod)}\s*$")
changed = False
for i, l in enumerate(lines):
    if action == "enable" and off.match(l):
        lines[i] = f"{off.match(l).group(1)}- {mod}"; changed = True
    elif action == "disable" and on.match(l):
        lines[i] = f"{on.match(l).group(1)}#  - {mod}"; changed = True
if not changed and not any(on.match(l) or off.match(l) for l in lines):
    sys.exit(f"module {mod!r} is not listed in {path}")
path.write_text("\n".join(lines) + "\n")
print("changed" if changed else "unchanged")
PY
}

case "$ACTION" in
  status)
    step "Platform modules (gitops/environments/demo/platform/kustomization.yaml)"; list_modules; exit 0 ;;
  enable|disable)
    [[ -n "$MODULE" && -d "${PLATFORM}/${MODULE}" ]] || die "usage: $0 enable|disable <module>  (modules: $(ls "$PLATFORM" | grep -v kustomization | xargs))"
    ;;
  *) die "unknown action: $ACTION" ;;
esac

step "${ACTION} module ${MODULE}"
res="$(toggle "$ACTION" "$MODULE")"; info "kustomization: ${res}"
hook="${PLATFORM}/${MODULE}/hooks/${ACTION}.sh"
if [[ "$ACTION" == "enable" ]]; then
  if kubectl config current-context 2>/dev/null | grep -q "^${CTX}$"; then
    step "Preloading the module's images"
    skip=1
    while IFS= read -r line; do
      if [[ "$line" =~ ^#\ ---\ module:\ ([a-z0-9-]+) ]]; then [[ "${BASH_REMATCH[1]}" == "$MODULE" ]] && skip=0 || skip=1; continue; fi
      [[ -z "$line" || "$line" == \#* || $skip -eq 1 ]] && continue
      docker image inspect "$line" >/dev/null 2>&1 || docker pull -q "$line" >/dev/null || { echo "    ! could not pull $line"; continue; }
      kind load docker-image --name "${CLUSTER}" "$line" >/dev/null 2>&1 && info "✓ $line"
    done < "${REPO_ROOT}/cluster/images.txt"
    step "Out-of-band state of the module"
    "${REPO_ROOT}/scripts/platform/03-secrets.sh" 2>/dev/null | grep -iA6 "$MODULE" | grep -E "created|kept" | sed 's/^/    /' || info "none"
  else
    info "no kind context ${CTX}: images and secrets will be handled by make up / make secrets"
  fi
fi
[[ -x "$hook" ]] && { step "hook ${MODULE}/hooks/${ACTION}.sh"; "$hook"; }

step "Coherence"
python3 "${REPO_ROOT}/scripts/repo/validate-coherence.py" | tail -1
if [[ "${COMMIT:-0}" == "1" ]]; then
  git -C "${REPO_ROOT}" add "$PLATFORM_KUSTOMIZATION"
  git -C "${REPO_ROOT}" commit -q -m "${ACTION} platform module ${MODULE}" && git -C "${REPO_ROOT}" push -q && info "committed and pushed: Argo CD applies it on its next poll (≤3 min)"
else
  info "now commit and push gitops/environments/demo/platform/kustomization.yaml (or rerun with COMMIT=1); Argo CD does the rest"
fi
