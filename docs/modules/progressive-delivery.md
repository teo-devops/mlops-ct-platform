# Module gap: progressive-delivery

| | |
|---|---|
| **Contract it would implement** | canary / blue-green traffic split with automated analysis and rollback |
| **Production counterpart** | Argo Rollouts with AnalysisTemplates on the Prometheus rules; or KServe canary (`canaryTrafficPercent`) behind a Gateway/Istio |
| **Where it plugs in** | a platform module (Rollouts) + the serving chart's `values-prod.yaml` (already shows `canaryTrafficPercent`) |
| **What stands in for it in the demo** | rolling update with readiness (zero downtime, no gradual traffic); rollback = `make promote` to the previous version |

The gate already prevents most bad promotions; progressive delivery protects against what offline replay cannot see (latency, integration).
