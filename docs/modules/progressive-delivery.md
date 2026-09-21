# Module: progressive-delivery (Argo Rollouts, opt-in)

| | |
|---|---|
| **Contract** | a workload declares a `Rollout` with a canary strategy; the platform provides the controller, the traffic split (ingress-nginx canary weights — no mesh on kind) and the judge: `ClusterAnalysisTemplate ct-slo`, on the api-metrics contract (`http_requests_total` 5xx ratio, p99 of `/v1/*`, `uc_fallback_total` ratio) restricted to the canary pods, with the thresholds of the SLO rules in `workloads/observability` |
| **Demo implementation** | Argo Rollouts controller + read-only dashboard at http://rollouts.localhost:8088; the analysis in `manifests/cluster-analysis-template.yaml` |
| **Pinned version** | chart 2.43.2 (Argo Rollouts v1.10.0) |
| **Namespace** | argo-rollouts (controller, dashboard); Rollouts in each workload's namespace |
| **Producers / consumers** | the use case's api chart renders a `Rollout` instead of its `Deployment` when `rollout.enabled` (steps: 20 % → pause → analysis → 50 % → pause → 100 %); its Application ignores the `rollouts-pod-template-hash` the controller stamps on the Service selectors |
| **Enable** | uncomment `- argo-rollouts` in `gitops/environments/demo/platform/kustomization.yaml`, commit; then `rollout.enabled: true` in the use case's `workloads/api/values-demo.yaml`, commit. The use case's Application has `prune: false`: delete the old Deployment by hand once (`kubectl -n <uc>-api delete deploy <uc>-api`), otherwise both serve. Nothing out of band |
| **Disable** | `rollout.enabled: false` (back to a Deployment) and comment the line |
| **In the demo** | off: rolling update with readiness, rollback = `make promote` to the previous version (decisions.md #12) |

Wave 2. What a canary protects against here: what the offline gate cannot see — latency, integration,
a lineage change that breaks the API — on the **API surface**. A promotion commit changes the API's
ConfigMap (`ALE_*_VERSION`), the pod template checksum changes, the Rollout starts: 20 % of the traffic
goes to the new pods, the platform's analysis reads their error ratio, p99 and fallback ratio for two
minutes, and only then the weight grows. A failed analysis aborts the rollout: the canary ReplicaSet is
scaled down, the stable one keeps 100 %, the Rollout (and its Application) is `Degraded` until a new
revision or `kubectl argo rollouts retry`.

What it does **not** do on kind, on purpose: the *model* itself is switched by KServe as soon as the
InferenceService's `storageUri` changes (Standard mode, no traffic split — decisions.md #8). A canary of
the model needs KServe Serverless / a mesh (`canaryTrafficPercent`, the serving chart's `values-prod.yaml`
shows it) or two InferenceServices behind the API. The Rollout judges the system with the new model
already serving; it can roll the API back, not the predictor — the registry alias `previous` and
`make promote` do that. With no traffic during a step every ratio is 0 and the step passes: send traffic
(or add a min-traffic measurement in production).
