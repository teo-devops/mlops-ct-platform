#!/usr/bin/env bash
# Runs the continuous-training pipeline for every model of the use case and
# waits for it. The first run bootstraps the models (version 0 -> 1): there is
# no separate "train" script — the pipeline is the only way a model gets to
# serving. Prints the promotion commit the pipeline pushed.
#
#   MODELS="categorizer fraud" TRIGGER=manual PROFILE="" ./scripts/40-run-pipeline.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require kubectl
require_kind_context

NS="listing-engine-pipelines"
MODELS="${MODELS:-categorizer fraud}"
TRIGGER="${TRIGGER:-manual}"
PROFILE="${PROFILE:-}"
TIMEOUT="${TIMEOUT:-900}"

kubectl -n "$NS" get workflowtemplate ct-pipeline >/dev/null 2>&1 || die "WorkflowTemplate ct-pipeline not synced yet (make status)"

declare -A WF
for model in $MODELS; do
  step "Submitting ct-pipeline for ${model} (trigger=${TRIGGER}${PROFILE:+, profile=$PROFILE})"
  name="$(kubectl -n "$NS" create -o name -f - <<EOT | cut -d/ -f2
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: ct-${model}-${TRIGGER}-
  labels:
    ct.mlops/model: ${model}
    ct.mlops/trigger: ${TRIGGER}
    ct.mlops/use-case: listing-engine
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
deadline=$(( $(date +%s) + TIMEOUT ))
for model in $MODELS; do
  name="${WF[$model]}"
  while true; do
    phase="$(kubectl -n "$NS" get workflow "$name" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    case "$phase" in
      Succeeded) info "✓ ${model}: ${name} Succeeded"; break ;;
      Failed|Error) kubectl -n "$NS" get workflow "$name" -o jsonpath='{.status.message}'; echo; die "${model}: ${name} ${phase}" ;;
    esac
    [[ $(date +%s) -lt $deadline ]] || die "timeout waiting for ${name}"
    sleep 10
  done
done

step "Outcome"
for model in $MODELS; do
  name="${WF[$model]}"
  kubectl -n "$NS" get workflow "$name" -o json | python3 -c '
import json,sys
wf=json.load(sys.stdin); nodes=wf["status"].get("nodes",{})
out={}
for n in nodes.values():
    if n.get("type")!="Pod": continue
    params={p["name"]:p.get("value") for p in n.get("outputs",{}).get("parameters",[])}
    out[n["displayName"]]=(n["phase"], params)
ev=out.get("evaluate",("-",{}))[1]
res=json.loads(ev.get("result","{}") or "{}")
print(f"    gate: promote={res.get(\"promote\")} ({res.get(\"reason\")}); candidate {res.get(\"primary_metric\")}={res.get(\"candidate\")} champion={res.get(\"champion\")}")
if "promote" in out:
    pr=json.loads(out["promote"][1].get("result","{}") or "{}")
    print(f"    promoted: version {pr.get(\"version\")} (previous {pr.get(\"previous_version\")}) commit {str(pr.get(\"commit\"))[:12]}")
else:
    print("    not promoted (register/promote skipped)")'
done
echo
info "Argo CD picks the promotion commit up on its next poll (≤3 min); watch: make status"
