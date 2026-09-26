# Architecture

The platform is a set of **infrastructure services behind contracts** (black boxes) plus a
**step contract** for pipelines. A use case brings its own workflows on top: its models, its
API, its pipeline definition, its secrets, its runbook. Nothing in the platform names a use case.

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│  USE CASES (plugins)      use-cases/<name>/  →  <name>-api · <name>-serving · <name>-pipelines │
├───────────────────────────────────────────────────────────────────────────────────────┤
│  SERVING             KServe (Standard mode)      contract: InferenceService + storageUri         │
│  CONTROL / MLOPS     MLflow · Argo Workflows     contracts: model-registry · orchestration        │
│  DATA                SeaweedFS                   contract: artifact-store (S3 API)                │
│  OBSERVABILITY       Prometheus · Grafana · Pushgateway · Evidently   contracts: monitoring · model-monitoring │
├───────────────────────────────────────────────────────────────────────────────────────┤
│  GITOPS ENGINE       Argo CD app-of-apps — every box above is an Application it reconciles       │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

## What the platform provides, what a use case brings

| The platform (black boxes) | A use case (workflows on top) |
|---|---|
| the contracts in [contracts.md](contracts.md) and their pinned implementations (`gitops/environments/<env>/platform/`) | a `UseCase` plugin: data source, schema, estimators, metrics, drift columns |
| the step CLI (`libs/ctsteps`): ingest → validate → preprocess → train → evaluate → register → promote, and `drift` | the image that runs the steps (`FROM ctsteps-base` + the plugin) |
| RBAC for pipeline namespaces, S3 identities per consumer, cluster-wide S3 defaults for serving | its three workloads (Helm charts): API, serving, pipelines — each its own namespace/AppProject/Application |
| generic alerting rules and the *CT Loop* dashboard (labels `use_case`, `model`) | its API (or none), its fallbacks, its SLO numbers |
| the bootstrap and operations scripts (`scripts/`) | its own scripts for the flow: build, run pipeline, promote, smoke, drift (`use-cases/<name>/scripts/`, wired to `make` through `USE_CASE=`) |
| the isolation model and the registration tooling | its group under `gitops/environments/<env>/{projects,apps}/<name>/` |

## The two paths every use case follows

**Synchronous** — a client request: ingress → `<name>-api` → parallel fan-out to the
InferenceServices of `<name>-serving` (KServe v1 protocol) → one combined answer, with lineage
(model versions, git commit, request id). The API logs every prediction to `s3://predictions/<name>/<model>/…`.

**Asynchronous** — the continuous-training loop ([ct-loop.md](ct-loop.md)): the prediction log →
`ct-drift` (CronWorkflow in `<name>-pipelines`, Evidently PSI against the champion's frozen
reference) → `ct_drift_*` metrics → above the retrain threshold, a `ct-pipeline` Workflow →
gates → registry → **a commit** bumping `models.<model>.version` → Argo CD sync → KServe rolls
the predictor with readiness checks. Weekly CronWorkflows retrain regardless of drift.

## Namespaces and network

| Namespace | Owner | Ingress allowed from | Egress allowed to |
|---|---|---|---|
| `<name>-api` | use case | ingress-nginx, observability | `<name>-serving` :8080, seaweedfs :9000 |
| `<name>-serving` | use case | `<name>-api`, observability | seaweedfs :9000 (storage-initializer) |
| `<name>-pipelines` | use case | — | seaweedfs, mlflow, pushgateway, API server, the Git forge (promote) |
| `seaweedfs` | shared workload | every consumer namespace, ingress-nginx, observability, host CIDR | intra-namespace |
| `mlflow`, `observability` | platform modules / shared | unrestricted ingress | unrestricted |
| `argocd`, `argo`, `kserve`, `cert-manager`, `ingress-nginx` | platform modules | no policies (webhooks come from the API server) | |

Policies are emitted by each workload's chart (the platform does not impose them) and enforced by
kindnet in the demo, by Cilium in the prod profile. DNS egress to `kube-system` is always allowed.
The `seaweedfs` chart's `networkPolicy.apiClients` list is where a new use case's namespaces are added.

## Isolation model (inherited from Argo-cd-Labs)

`1 workload = 1 namespace = 1 AppProject = 1 Application` (= 1 directory of this monorepo). A
workload's AppProject may read only this repository and write only its own namespace; it may not
create RBAC. Everything cluster-scoped — CRDs, webhooks, ClusterRoles, the RBAC that pipelines
need — belongs to the `platform` project. Applications carry the label
`mlops-ct-platform.dev/group` (`shared` or the use-case name), which is how platform scripts tell
platform workloads from use-case workloads without knowing any use case. Secrets are never in Git
([secrets.md](secrets.md)).

The concrete instance of all this for a use case is in its own docs: `use-cases/<name>/docs/architecture.md` ([use-cases/README.md](../../use-cases/README.md) lists them).
