#!/usr/bin/env bash
# When the Rollouts controller goes, the `rollouts-pod-template-hash` it stamped
# on the stable/canary Services stays and selects no pod (503). Clean it on
# every Service of every use case that used a Rollout.
. "$(dirname "${BASH_SOURCE[0]}")/../../../../../../scripts/lib.sh"
kubectl config current-context 2>/dev/null | grep -q "^${CTX}$" || { echo "    no kind context; nothing to clean"; exit 0; }
for ref in $(kubectl get svc -A -o json | python3 -c '
import json,sys
for s in json.load(sys.stdin)["items"]:
    if "rollouts-pod-template-hash" in (s["spec"].get("selector") or {}):
        print(s["metadata"]["namespace"] + "/" + s["metadata"]["name"])'); do
  kubectl -n "${ref%/*}" patch svc "${ref#*/}" --type json -p '[{"op":"remove","path":"/spec/selector/rollouts-pod-template-hash"}]' >/dev/null && echo "    ✓ selector cleaned on ${ref}"
done
echo "    remember: rollout.enabled: false in the use cases' api values-demo.yaml"
