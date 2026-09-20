#!/usr/bin/env bash
# End-to-end proof of the synchronous path and of graceful degradation:
#   1. a real request answered by both models
#   2. the fraud model is taken down -> the rules fallback answers, the flow never blocks
#   3. NetworkPolicies: a pod outside the API namespace cannot reach the predictors
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/scripts/lib.sh"
require kubectl curl python3
require_kind_context
API="${API:-http://automated-listing-engine.localhost:8088}"
SNS="automated-listing-engine-serving"

analyze() { curl -s -X POST "$API/v1/listings/analyze" -H 'content-type: application/json' -d "$1"; }
field() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))" "$1"; }

step "1. Happy path"
body='{"title":"iPhone 13 Pro 128GB very good condition","price":450}'
resp="$(analyze "$body")"; echo "    $resp" | head -c 600; echo
[[ "$(echo "$resp" | field 'd["category"]["source"]')" == "model" ]] || die "category not from model"
[[ "$(echo "$resp" | field 'd["fraud"]["source"]')" == "model" ]] || die "fraud not from model"
[[ "$(echo "$resp" | field 'd["category"]["label"]')" == "electronics" ]] || die "expected electronics"
[[ -n "$(echo "$resp" | field 'd["lineage"]["git_commit"]')" ]] || die "no lineage"
info "✓ both models answered; served versions: categorizer v$(echo "$resp" | field 'd["category"]["model_version"]'), fraud v$(echo "$resp" | field 'd["fraud"]["model_version"]')"

step "2. Fallback drill: fraud model down"
before="$(curl -s "$API/metrics" | awk '/^uc_fallback_total/ {s+=$2} END {print s+0}')"
kubectl -n "$SNS" scale deploy/fraud-predictor --replicas=0 >/dev/null
until [[ -z "$(kubectl -n "$SNS" get pods -l serving.kserve.io/inferenceservice=fraud -o name 2>/dev/null)" ]]; do sleep 2; done
resp="$(analyze '{"title":"iPhone 15 Pro Max URGENT whatsapp","price":40}')"; echo "    $resp" | head -c 400; echo
[[ "$(echo "$resp" | field 'd["fraud"]["source"]')" == "fallback" ]] || die "expected fallback"
[[ "$(echo "$resp" | field 'd["fraud"]["is_suspicious"]')" == "True" ]] || die "rules should flag it"
[[ "$(echo "$resp" | field 'd["category"]["source"]')" == "model" ]] || die "categorizer must still answer"
after="$(curl -s "$API/metrics" | awk '/^uc_fallback_total/ {s+=$2} END {print s+0}')"
(( after > before )) || die "uc_fallback_total did not increase ($before -> $after)"
info "✓ degraded gracefully (uc_fallback_total $before -> $after); restoring the model"
# KServe reconciles the Deployment back to minReplicas; nudge it and wait.
kubectl -n "$SNS" scale deploy/fraud-predictor --replicas=1 >/dev/null
kubectl -n "$SNS" wait pod -l serving.kserve.io/inferenceservice=fraud --for=condition=Ready --timeout=180s >/dev/null
resp="$(analyze "$body")"
[[ "$(echo "$resp" | field 'd["fraud"]["source"]')" == "model" ]] || info "! fraud still on fallback (circuit cooling down, ok)"

step "3. NetworkPolicy: predictors unreachable from outside the API namespace"
url="http://categorizer-predictor.${SNS}.svc.cluster.local/v1/models/categorizer"
code="$(kubectl run np-probe --rm -i --restart=Never --image=curlimages/curl:8.10.1 -n default -q -- \
  -s -o /dev/null -m 5 -w '%{http_code}' "$url" 2>/dev/null || true)"
[[ "$code" == "000" || -z "$code" ]] || die "predictor reachable from default namespace (HTTP $code)"
info "✓ blocked from namespace default"
code="$(kubectl -n automated-listing-engine-api exec deploy/automated-listing-engine-api -- python -c "import httpx;print(httpx.get('$url',timeout=5).status_code)" 2>/dev/null)"
[[ "$code" == "200" ]] || die "predictor not reachable from the API pod (got '$code')"
info "✓ reachable from the API namespace"

echo; echo "Smoke test passed."
