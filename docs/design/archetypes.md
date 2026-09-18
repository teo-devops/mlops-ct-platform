# Workload archetypes

The annotation `mlops-ct-platform.dev/archetype` on an Application documents how a workload
behaves under GitOps; the validator only checks it is one of these. Inherited from Argo-cd-Labs.

| Archetype | Examples here | What to know |
|---|---|---|
| `stateless` | a use case's API and serving workloads, `observability` | replicas are declared by the chart; with an HPA, do not declare `replicas` (self-heal would fight it) |
| `stateful` | minio | PVCs carry `argocd.argoproj.io/sync-options: Prune=false` from the first commit; `strategy: Recreate` for RWO volumes; hooks (the provisioning Job) run PostSync and are recreated each sync |
| `batch` | — | a Job is immutable (`Replace=true` on that resource only); with self-heal, deleting a finished Job re-runs it |
| `pipeline` | a use case's pipelines workload | WorkflowTemplates and CronWorkflows are declared; Workflows are runtime objects created by the controller, the monitor or a human and are **not** in Git (the AppProject's orphan warning ignores nothing, so they show as orphans — by design) |
