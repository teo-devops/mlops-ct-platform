#!/usr/bin/env bash
# Runs the continuous-training pipeline for every model of the use case and
# waits for it. The first run bootstraps the models (version 0 -> 1): there is
# no separate "train" script — the pipeline is the only way a model gets to
# serving. Prints the promotion commit the pipeline pushed.
#
#   USE_CASE=<uc> [MODELS="a b"] [TRIGGER=manual] [PROFILE=""] scripts/use-case/07-run-pipeline.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib-uc.sh"
require kubectl
require_kind_context

NS="$UC_NS_PIPELINES"
MODELS="${MODELS:-$UC_MODELS}"
TRIGGER="${TRIGGER:-manual}"
PROFILE="${PROFILE:-}"
TIMEOUT="${TIMEOUT:-900}"

kubectl -n "$NS" get workflowtemplate ct-pipeline >/dev/null 2>&1 || die "WorkflowTemplate ct-pipeline not synced yet (make status)"

declare -A WF
for model in $MODELS; do
  step "Submitting ct-pipeline for ${UC_NAME}/${model} (trigger=${TRIGGER}${PROFILE:+, profile=$PROFILE})"
  name="$(kubectl -n "$NS" create -o name -f - <<EOT | cut -d/ -f2
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: ct-${model}-${TRIGGER}-
  labels:
    ct.mlops/model: ${model}
    ct.mlops/trigger: ${TRIGGER}
    ct.mlops/use-case: ${UC_NAME}
spec:
  workflowTemplateRef:
    name: ct-pipeline
  arguments:
    parameters:
      - {name: model, value: "${model}"}
      - {name: trigger, value: "${TRIGGER}"}
      - {name: profile, value: "${PROFILE}"}
EOT
)"
  WF[$model]="$name"
  info "workflow ${name}  →  http://argo.localhost:8088/workflows/${NS}/${name}"
done

step "Waiting for completion (timeout ${TIMEOUT}s)"
for model in $MODELS; do
  wf_wait "$NS" "${WF[$model]}" "$TIMEOUT" && info "✓ ${model}: ${WF[$model]} Succeeded"
done

step "Outcome"
for model in $MODELS; do
  kubectl -n "$NS" get workflow "${WF[$model]}" -o json | python3 -c '
import json,sys
wf=json.load(sys.stdin); nodes=wf["status"].get("nodes",{})
out={}
for n in nodes.values():
    if n.get("type")!="Pod": continue
    params={p["name"]:p.get("value") for p in n.get("outputs",{}).get("parameters",[])}
    out[n["displayName"]]=(n["phase"], params)
ev=out.get("evaluate",("-",{}))[1]
res=json.loads(ev.get("result","{}") or "{}")
print("    gate: promote=%s (%s); candidate %s=%s champion=%s" % (res.get("promote"), res.get("reason"), res.get("primary_metric"), res.get("candidate"), res.get("champion")))
if "promote" in out:
    pr=json.loads(out["promote"][1].get("result","{}") or "{}")
    print("    promoted: version %s (previous %s) commit %s" % (pr.get("version"), pr.get("previous_version"), str(pr.get("commit"))[:12]))
else:
    print("    not promoted (register/promote skipped)")'
done
echo
info "Argo CD picks the promotion commit up on its next poll (≤3 min); watch: make status"
