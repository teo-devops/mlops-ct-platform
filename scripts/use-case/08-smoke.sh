#!/usr/bin/env bash
# Smoke test of a use case's API, knowing nothing about its payloads: the
# sample request from usecase.yaml must answer 200 with the platform's lineage;
# the served versions come from the api-metrics contract; if the use case names
# a degradable model, killing its predictor must not break the API (fallback
# counted); the predictors are unreachable from outside the API namespace.
. "$(dirname "${BASH_SOURCE[0]}")/lib-uc.sh"
require kubectl curl python3
require_kind_context
[[ "$UC_API_ENABLED" == "true" ]] || { info "${UC_NAME}: no API declared, nothing to smoke"; exit 0; }
API="$UC_API"; SNS="$UC_NS_SERVING"

call() { curl -s -o /tmp/ct-smoke-body -w '%{http_code}' -X POST "${API}${UC_API_PATH}" -H 'content-type: application/json' -d "$1"; }
fallbacks() { curl -s "${API}/metrics" | awk -v uc="$UC_NAME" '$1 ~ /^uc_fallback_total\{/ && index($0, "use_case=\"" uc "\"") {s+=$2} END {print s+0}'; }

step "1. Happy path: ${UC_API_PATH}"
code="$(call "$UC_API_SAMPLE")"
info "$(head -c 400 /tmp/ct-smoke-body)"; echo
[[ "$code" == "200" ]] || die "expected 200, got ${code}"
python3 - "$UC_NAME" /tmp/ct-smoke-body <<'PY'
import json, sys
d = json.load(open(sys.argv[2]))
lineage = d.get("lineage") or {}
assert lineage.get("use_case") == sys.argv[1], f"lineage.use_case != {sys.argv[1]}: {lineage}"
assert lineage.get("git_commit") and lineage.get("request_id"), f"lineage incomplete: {lineage}"
PY
info "✓ answered with lineage; served versions: $(uc_served_versions)"

if [[ -n "$UC_API_DEGRADABLE_MODEL" ]]; then
  m="$UC_API_DEGRADABLE_MODEL"
  step "2. Fallback drill: ${m} model down"
  before="$(fallbacks)"
  kubectl -n "$SNS" scale deploy/${m}-predictor --replicas=0 >/dev/null
  kubectl -n "$SNS" wait --for=delete pod -l serving.kserve.io/inferenceservice="$m" --timeout=60s >/dev/null 2>&1 || true
  code="$(call "$UC_API_SAMPLE")"
  [[ "$code" == "200" ]] || die "the API must keep answering without ${m}; got ${code}"
  after="$(fallbacks)"
  [[ "$after" -gt "$before" ]] || die "uc_fallback_total did not grow (${before} -> ${after})"
  info "✓ degraded gracefully (uc_fallback_total ${before} -> ${after}); restoring the model"
  kubectl -n "$SNS" scale deploy/${m}-predictor --replicas=1 >/dev/null
  kubectl -n "$SNS" wait --for=condition=ready pod -l serving.kserve.io/inferenceservice="$m" --timeout=180s >/dev/null 2>&1 || true
else
  step "2. Fallback drill: skipped (no degradable model declared)"
fi

step "3. NetworkPolicy: predictors unreachable from outside the API namespace"
url="http://${UC_FIRST_MODEL}-predictor.${SNS}.svc.cluster.local/v1/models/${UC_FIRST_MODEL}"
code="$(kubectl run np-probe --rm -i --restart=Never --image=curlimages/curl:8.10.1 -n default -q -- \
  -s -o /dev/null -m 5 -w '%{http_code}' "$url" 2>/dev/null || true)"
[[ "$code" == "000" || -z "$code" ]] || die "predictor reachable from default namespace (HTTP $code)"
info "✓ blocked from namespace default"
pod="$(kubectl -n "$UC_NS_API" get pod -l app.kubernetes.io/name="${UC_NAME}-api" -o name | head -1)"
code="$(kubectl -n "$UC_NS_API" exec "$pod" -- python -c "import httpx;print(httpx.get('$url',timeout=5).status_code)" 2>/dev/null || echo 000)"
[[ "$code" == "200" ]] || die "predictor NOT reachable from the API namespace (got ${code})"
info "✓ reachable from the API namespace"
echo; echo "Smoke test passed."
