#!/usr/bin/env bash
# Promote a registered model version by hand — or roll back to a previous one.
#   ./use-cases/automated-listing-engine/scripts/promote.sh <model> <version> [trigger]
# It runs the same `promote` step as the pipeline: registry alias + one commit
# bumping the served version. Rollback = promote the previous version.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/scripts/lib.sh"
require kubectl
require_kind_context
MODEL="${1:?model}"; VERSION="${2:?version}"; TRIGGER="${3:-manual}"
NS="automated-listing-engine-pipelines"
name="$(kubectl -n "$NS" create -o name -f - <<EOT | cut -d/ -f2
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: ct-${MODEL}-promote-
spec:
  workflowTemplateRef:
    name: ct-promote
  arguments:
    parameters:
      - {name: model, value: "${MODEL}"}
      - {name: version, value: "${VERSION}"}
      - {name: trigger, value: "${TRIGGER}"}
EOT
)"
step "Promoting ${MODEL} v${VERSION} (${name})"
while true; do
  phase="$(kubectl -n "$NS" get workflow "$name" -o jsonpath='{.status.phase}')"
  case "$phase" in Succeeded) break ;; Failed|Error) die "$name $phase" ;; esac
  sleep 5
done
kubectl -n "$NS" get workflow "$name" -o json | python3 -c '
import json,sys; wf=json.load(sys.stdin)
for n in wf["status"]["nodes"].values():
    if n.get("type")=="Pod":
        r=json.loads({p["name"]:p.get("value") for p in n["outputs"]["parameters"]}.get("result") or "{}")
        print("    version", r.get("version"), "(previous", r.get("previous_version"), ") commit", str(r.get("commit"))[:12])'
