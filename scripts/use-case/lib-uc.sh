#!/usr/bin/env bash
# Loads use-cases/$USE_CASE/usecase.yaml into UC_* variables. Sourced by the
# flow scripts; the platform never hardcodes a use case.
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
USE_CASE="${USE_CASE:?USE_CASE required (make USE_CASE=<name> ...)}"
UC_DIR="${REPO_ROOT}/use-cases/${USE_CASE}"
UC_FILE="${UC_DIR}/usecase.yaml"
[[ -f "$UC_FILE" ]] || die "no such use case: ${UC_FILE}"
eval "$(python3 - "$UC_FILE" <<'PY'
import json, shlex, sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
api = d.get("api") or {}
drift = d.get("drift") or {}
out = {
    "UC_NAME": d["name"], "UC_PACKAGE": d["package"], "UC_MODELS": " ".join(d["models"]),
    "UC_API_ENABLED": str(bool(api.get("enabled", False))).lower(),
    "UC_API_HOST": api.get("host", ""), "UC_API_PATH": api.get("path", ""),
    "UC_API_SAMPLE": json.dumps(api.get("sample") or {}),
    "UC_API_DEGRADABLE_MODEL": api.get("degradable_model") or "",
    "UC_DRIFT_PROFILE": drift.get("profile", "drift"), "UC_DRIFT_REQUESTS": str(drift.get("requests", 600)),
}
for k, v in out.items():
    print(f"{k}={shlex.quote(v)}")
PY
)"
[[ "$UC_NAME" == "$USE_CASE" ]] || die "usecase.yaml name (${UC_NAME}) != directory (${USE_CASE})"
UC_NS_API="${UC_NAME}-api"; UC_NS_SERVING="${UC_NAME}-serving"; UC_NS_PIPELINES="${UC_NAME}-pipelines"
UC_API="${API:-http://${UC_API_HOST}:8088}"
UC_FIRST_MODEL="${UC_MODELS%% *}"
# Wait for an Argo Workflow to finish; dies on failure.
wf_wait() { # <ns> <name> [timeout]
  local ns="$1" name="$2" deadline=$(( $(date +%s) + ${3:-900} )) phase
  while true; do
    phase="$(kubectl -n "$ns" get workflow "$name" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    case "$phase" in
      Succeeded) return 0 ;;
      Failed|Error) kubectl -n "$ns" get workflow "$name" -o jsonpath='{.status.message}'; echo; die "$name $phase" ;;
    esac
    [[ $(date +%s) -lt $deadline ]] || die "timeout waiting for $name"
    sleep 5
  done
}
# Served version of every model, as the API reports it in uc_predictions_total.
uc_served_versions() {
  curl -s "${UC_API}/metrics" 2>/dev/null | python3 -c '
import re, sys
seen = {}
for line in sys.stdin:
    m = re.match(r"uc_predictions_total\{(.*)\} ([0-9.e+]+)", line)
    if not m: continue
    labels = dict(kv.split("=", 1) for kv in m.group(1).split(","))
    model, ver = labels.get("model", "").strip("\""), labels.get("model_version", "").strip("\"")
    if labels.get("source", "").strip("\"") == "model": seen[model] = ver
print(" ".join(f"{m}={v}" for m, v in sorted(seen.items())))'
}
