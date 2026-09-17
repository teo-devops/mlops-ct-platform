#!/usr/bin/env bash
# The closed loop, end to end:
#   1. send "post-season" traffic to the API (prices collapse, electronics
#      floods the marketplace, new vocabulary) — the prediction log fills up
#   2. run the drift monitor now (the CronWorkflow would do it within 10 min)
#   3. PSI > retrain threshold -> the monitor submits ct-pipeline (trigger=drift)
#   4. the pipeline trains on the new world, beats the champion on the new
#      holdout, registers, promotes: a commit bumps the served version
#   5. Argo CD syncs, KServe rolls the predictor, the API reports the new version
#
#   REQUESTS=600 ./scripts/55-induce-drift.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require kubectl curl python3 git
require_kind_context
API="${API:-http://listing-engine.localhost:8088}"
NS="listing-engine-pipelines"
REQUESTS="${REQUESTS:-600}"

before_versions="$(curl -s -X POST "$API/v1/listings/analyze" -H 'content-type: application/json' \
  -d '{"title":"laptop used","price":300}' | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["category"]["model_version"], d["fraud"]["model_version"])')"
info "served versions before: categorizer/fraud = ${before_versions}"

step "1. The world changes: the data source now delivers post-season data"
# What the upstream data platform would do on its own; the pipeline's ingest
# reads this ConfigMap. Traffic below comes from the same new world.
kubectl -n "$NS" create configmap ct-data-source --from-literal=profile=drift --dry-run=client -o yaml | kubectl apply -f - >/dev/null
info "ct-data-source.profile = drift"

step "2. Sending ${REQUESTS} drifted listings (prices collapse, electronics floods, new vocabulary)"
python3 - "$API" "$REQUESTS" <<'PY'
import json, random, sys, urllib.request, time
api, n = sys.argv[1], int(sys.argv[2])
random.seed(7)
vocab = {
  "electronics": ["iphone","samsung","laptop","headphones","tablet","camera","ps5","monitor","gpu","smartwatch",
                  "foldable","e-bike","drone","vr headset","airpods","foldable","e-bike","drone","vr headset","airpods"],
  "fashion": ["jacket","sneakers","dress","jeans","handbag","coat","boots","y2k","thrift","cargo"],
  "home": ["sofa","table","lamp","chair","shelf"], "sports": ["bike","skis","tennis","dumbbells","helmet"],
  "books": ["novel","textbook","comic","manga"], "kids": ["stroller","lego","crib","toy","scooter"],
}
median = {"electronics":350,"fashion":40,"home":90,"sports":120,"books":12,"kids":45}
qual = ["new","like new","used","good condition","vintage","original","sealed","barely used","2023","pro"]
cats, w = list(vocab), [0.55,0.15,0.08,0.07,0.08,0.07]
ok = err = 0
for i in range(n):
    c = random.choices(cats, w)[0]
    words = [random.choice(vocab[c]), random.choice(qual)] + ([random.choice(vocab[c])] if random.random()<0.5 else [])
    price = round(max(0.5, random.lognormvariate(__import__("math").log(median[c]), 0.7) * 0.35), 2)
    body = json.dumps({"title": " ".join(words), "price": price}).encode()
    req = urllib.request.Request(f"{api}/v1/listings/analyze", data=body, headers={"content-type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5).read(); ok += 1
    except Exception:
        err += 1
    if i % 100 == 99:
        print(f"    {i+1} sent ({err} errors)", flush=True)
print(f"    done: {ok} ok, {err} errors")
PY
info "waiting for the API to flush its prediction-log buffer"
sleep 15

step "3. Running the drift monitor now"
name="$(kubectl -n "$NS" create -o name -f - <<EOT | cut -d/ -f2
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: ct-drift-manual-
spec:
  workflowTemplateRef:
    name: ct-drift
EOT
)"
while true; do
  phase="$(kubectl -n "$NS" get workflow "$name" -o jsonpath='{.status.phase}')"
  case "$phase" in Succeeded) break ;; Failed|Error) die "drift monitor $name $phase" ;; esac
  sleep 5
done
kubectl -n "$NS" get workflow "$name" -o json | python3 -c '
import json,sys; wf=json.load(sys.stdin)
for n in wf["status"]["nodes"].values():
    if n.get("type")=="Pod":
        r=json.loads({p["name"]:p.get("value") for p in n.get("outputs",{}).get("parameters",[])}.get("result") or "{}")
        print("    %-18s level=%s max_psi=%s rows=%s retrain=%s psi=%s" % (n["displayName"], r.get("level", r.get("skipped")), r.get("max_psi"), r.get("rows"), r.get("retrain_submitted") or "-", r.get("psi")))'

step "4. Retraining pipelines submitted by the monitor"
retrains="$(kubectl -n "$NS" get workflows -l ct.mlops/trigger=drift --sort-by=.metadata.creationTimestamp -o name | tail -2 | cut -d/ -f2)"
[[ -n "$retrains" ]] || die "the monitor did not submit any retrain (PSI below threshold?)"
for wf in $retrains; do
  info "waiting for $wf"
  while true; do
    phase="$(kubectl -n "$NS" get workflow "$wf" -o jsonpath='{.status.phase}')"
    case "$phase" in Succeeded) info "✓ $wf Succeeded"; break ;; Failed|Error) die "$wf $phase" ;; esac
    sleep 10
  done
done

step "5. Promotion commits pushed by the pipeline"
git -C "${REPO_ROOT}" fetch -q origin
git -C "${REPO_ROOT}" log origin/main --oneline -4 | grep "ct: promote" | sed 's/^/    /' || info "no promotion (gate refused: candidate did not beat the champion)"

step "6. Waiting for the new versions to be served"
for _ in $(seq 1 40); do
  kubectl -n argocd annotate application listing-engine-serving listing-engine-api argocd.argoproj.io/refresh=normal --overwrite >/dev/null 2>&1
  now="$(curl -s -X POST "$API/v1/listings/analyze" -H 'content-type: application/json' \
    -d '{"title":"laptop used","price":300}' | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["category"]["model_version"], d["fraud"]["model_version"])' 2>/dev/null || true)"
  [[ -n "$now" && "$now" != "$before_versions" ]] && break
  sleep 15
done
info "served versions after:  categorizer/fraud = ${now:-?}   (before: ${before_versions})"
echo; echo "Closed loop demonstrated: drift -> retrain -> gate -> promote (commit) -> GitOps sync -> new version served."
