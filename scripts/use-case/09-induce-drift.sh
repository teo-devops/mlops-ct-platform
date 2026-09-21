#!/usr/bin/env bash
# The closed loop, end to end, for one use case: the world changes (the data
# source switches to the use case's drift profile), the API receives traffic
# from that new world, the drift monitor measures PSI, submits the retraining
# pipelines, the gate accepts the challengers, promote commits, Argo CD syncs,
# the new versions are served. Nothing here knows the use case's columns: the
# traffic comes from `ctsteps sample` inside the use case's own steps image.
#
#   USE_CASE=<uc> [REQUESTS=600] scripts/use-case/09-induce-drift.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib-uc.sh"
require kubectl curl docker python3 git
require_kind_context
[[ "$UC_API_ENABLED" == "true" ]] || die "${UC_NAME} has no API: the drift monitor reads the API's prediction log"
API="$UC_API"; NS="$UC_NS_PIPELINES"
REQUESTS="${REQUESTS:-$UC_DRIFT_REQUESTS}"; PROFILE="$UC_DRIFT_PROFILE"
N_MODELS="$(echo "$UC_MODELS" | wc -w)"

step "0. Served versions before"
before="$(uc_served_versions)"; info "${before:-none yet (send a request first: make smoke)}"

step "1. The world changes: the data source now delivers profile '${PROFILE}'"
kubectl -n "$NS" create configmap ct-data-source --from-literal=profile="${PROFILE}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
info "ct-data-source.profile = ${PROFILE}"

step "2. Sending ${REQUESTS} requests from that world (ctsteps sample, profile=${PROFILE})"
docker run --rm "${UC_NAME}-steps:${VERSION:-0.1.0}" \
  ctsteps sample --use-case "${UC_PACKAGE}:use_case" --model "${UC_FIRST_MODEL}" --rows "${REQUESTS}" --seed 7 --profile "${PROFILE}" \
  > /tmp/ct-drift-traffic.json
python3 - "${API}${UC_API_PATH}" /tmp/ct-drift-traffic.json <<'PY'
import json, sys, urllib.request
url, path = sys.argv[1], sys.argv[2]
ok = err = 0
for i, row in enumerate(json.load(open(path))):
    req = urllib.request.Request(url, data=json.dumps(row).encode(), headers={"content-type": "application/json"})
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
wf_wait "$NS" "$name"
kubectl -n "$NS" get workflow "$name" -o json | python3 -c '
import json,sys; wf=json.load(sys.stdin)
for n in wf["status"]["nodes"].values():
    if n.get("type")=="Pod":
        r=json.loads({p["name"]:p.get("value") for p in n.get("outputs",{}).get("parameters",[])}.get("result") or "{}")
        print("    %-18s level=%s max_psi=%s rows=%s source=%s retrain=%s psi=%s" % (n["displayName"], r.get("level", r.get("skipped")), r.get("max_psi"), r.get("rows"), r.get("source"), r.get("retrain_submitted") or "-", r.get("psi")))'

step "4. Retraining pipelines submitted by the monitor"
retrains="$(kubectl -n "$NS" get workflows -l ct.mlops/trigger=drift --sort-by=.metadata.creationTimestamp -o name | tail -"$N_MODELS" | cut -d/ -f2)"
[[ -n "$retrains" ]] || die "the monitor did not submit any retrain (PSI below threshold?)"
for wf in $retrains; do
  info "waiting for $wf"; wf_wait "$NS" "$wf" && info "✓ $wf Succeeded"
done

step "5. Promotion commits pushed by the pipeline"
git -C "${REPO_ROOT}" fetch -q origin
git -C "${REPO_ROOT}" log origin/main --oneline -8 | grep "ct: promote ${UC_NAME}/" | head -"$N_MODELS" | sed 's/^/    /' || info "no promotion (gate refused: candidate did not beat the champion)"

step "6. Waiting for the new versions to be served"
for _ in $(seq 1 40); do
  kubectl -n argocd annotate application "${UC_NAME}-serving" "${UC_NAME}-api" argocd.argoproj.io/refresh=normal --overwrite >/dev/null 2>&1
  curl -s -o /dev/null -X POST "${API}${UC_API_PATH}" -H 'content-type: application/json' -d "$UC_API_SAMPLE"
  now="$(uc_served_versions)"
  [[ -n "$now" && "$now" != "$before" ]] && break
  sleep 15
done
info "served versions after:  ${now:-?}   (before: ${before:-?})"
echo; echo "Closed loop demonstrated: drift -> retrain -> gate -> promote (commit) -> GitOps sync -> new version served."
