# mlops-ct-platform

A tool-agnostic MLOps platform that runs a **closed continuous-training loop** on a laptop-sized
Kubernetes cluster (kind), end to end and for real:

```
ingest → validate (gate) → train → evaluate champion/challenger (gate) → register
   → promote (a Git commit) → serve without downtime → monitor drift (PSI) → retrain
```

Every tool sits behind a **contract** — artifact store, model registry, serving, orchestration,
monitoring, model monitoring — and is a self-contained, pinned **module** that can be swapped or
disabled without touching anything else. The example use case, the *Listing Engine* (categorise a
marketplace listing and flag fraud, inspired by a real hiring case study), is a **plugin**: the
platform never mentions it.

| What you get | Where |
|---|---|
| GitOps control plane (Argo CD app-of-apps, one AppProject per workload) | `gitops/` — `bootstrap/`, `argo-cd/`, `templates/`, `environments/demo/` |
| Platform modules: cert-manager, KServe, MLflow, Argo Workflows, Prometheus/Grafana, Pushgateway | `gitops/environments/demo/platform/<module>/` |
| Workload registrations, grouped by owner (`shared/`, `<use-case>/`) | `gitops/environments/demo/{projects,apps}/<group>/` |
| Shared workloads: MinIO with per-consumer users, CT alerting rules and dashboards | `workloads/` |
| The step contract: pipeline steps as containers, orchestrator-agnostic | `libs/ctsteps/` |
| Orchestrator adapters (Argo Workflows runs the demo; Airflow/KFP as reference) | `pipelines/` |
| The example use case: plugin, API with graceful degradation, its three workloads | `use-cases/listing-engine/` |
| kind cluster definition and the images preloaded into it | `cluster/` |
| Docs: architecture, contracts, module cards, decisions, profiles (kind / bare-metal / AWS) | `docs/` |

## Quickstart (≈15 minutes on a laptop)

Requirements: Docker, kind ≥ 0.31, kubectl, helm ≥ 3.14, python ≥ 3.11 with PyYAML, `gh` logged in
(the repository is private for now; Argo CD needs a read token) — `make prereqs` checks them.

```bash
make up          # kind cluster + ingress-nginx + image preload (~5 min)
make secrets     # namespaces and demo Secrets (random, cluster-only, never in Git)
make bootstrap   # Argo CD from the chart, then root-app: everything else arrives by GitOps
make wait        # platform modules Synced/Healthy
make build       # use-case images -> kind
make pipeline    # first run of the CT pipeline for both models: version 0 -> 1
make smoke       # real request, fallback drill, network-policy probe
make drift       # the world changes -> drift -> retrain -> promote commit -> new version served
make status      # URLs and passwords: argocd | argo | mlflow | grafana | prometheus | minio .localhost:8088
make down
```

`make demo` chains the first seven. Every UI answers on `http://<name>.localhost:8088`.

## What the demo proves

* **No model is deployed by hand.** A model reaches serving only through the pipeline: the gate
  (`evaluate`) compares the candidate with the current champion on the same held-out data; `promote`
  sets the registry alias and **pushes a commit** that bumps the served version. Argo CD syncs it,
  KServe rolls the predictor with readiness checks. Rollback = `make promote MODEL=fraud VERSION=1`
  (the same step, another commit).
* **Silent failure is caught by distributions, not by errors.** The API logs every prediction to the
  artifact store; the drift monitor (Evidently, PSI) compares the champion's frozen training
  reference with the live window every 10 minutes and, above the retrain threshold, submits the
  pipeline itself. `make drift` shows the whole loop in ~5 minutes:

  ```
  drift-categorizer  level=retrain max_psi=0.3285 rows=1205 retrain=ct-categorizer-drift-j7m77
  ✓ ct-categorizer-drift-j7m77 Succeeded          gate: f1_macro improved by 0.1511 (0.99 vs 0.84)
  46e44d1 ct: promote listing-engine/categorizer v2 (trigger=drift)
  served versions after: categorizer/fraud = 2 1   (before: 1 1)
  ```
* **Degradation is a product decision.** When the fraud model is slow, down or fused (circuit
  breaker), the API answers with explainable rules and the listing flow never blocks; the
  categorizer is required and fails loud (503).
* **Isolation is declared, not assumed.** `1 workload = 1 namespace = 1 AppProject = 1 Application`;
  every workload ships its own NetworkPolicies; the smoke test proves a pod outside the API
  namespace cannot reach the predictors.
* **Same charts, different values.** `gitops/environments/demo` is what runs; `gitops/environments/prod` and
  `gitops/environments/aws` show the same modules with production values (docs/profiles.md).

## Repository map

```
gitops/                 what Argo CD reconciles, and how it is bootstrapped
  bootstrap/            root-app (applied once by scripts/platform/install.sh)
  argo-cd/values.yaml   the engine's single source of configuration
  templates/            AppProject + Application templates for new workloads
  environments/demo/    the environment that runs on kind (prod/ and aws/ are documented shapes)
    platform/<module>/  one directory per platform module: pinned chart + values (+ manifests)
    projects/<group>/   one AppProject per workload   ┐ groups: shared/, listing-engine/, …
    apps/<group>/       one Application per workload  ┘ (scripts/repo/register-workload.py --group)
cluster/                kind.yaml and the image preload list
workloads/              charts of the shared workloads (minio, observability)
use-cases/<name>/       a use case: plugin (steps image), api, workloads/{api,serving,pipelines}
libs/ctsteps/           the step contract (python package + CLI + tests)
pipelines/              orchestrator adapters and notes
scripts/                cluster/ · platform/ · demo/ · repo/ — see scripts/README.md; paths resolve from the repo root
docs/                   start with architecture.md and contracts.md
```

## Read next

* [docs/architecture.md](docs/architecture.md) — domains, the synchronous and asynchronous paths, network
* [docs/contracts.md](docs/contracts.md) — the six contracts and the step CLI
* [docs/ct-loop.md](docs/ct-loop.md) — the loop step by step, with what each step reads and writes
* [docs/modules/](docs/modules/) — one card per module, including the gaps (Kafka, Feast, Katib, Great Expectations, Argo Rollouts)
* [docs/decisions.md](docs/decisions.md) — ADRs: why Argo Workflows and not Airflow in kind, sqlite, MinIO, push vs PR…
* [docs/case-study.md](docs/case-study.md) — the Listing Engine case: symptoms → which module fixes what, SLOs, ownership
* [docs/what-the-demo-does-not-prove.md](docs/what-the-demo-does-not-prove.md) — read this before extrapolating

The GitOps control plane is inherited from [teo-devops/Argo-cd-Labs](https://github.com/teo-devops/Argo-cd-Labs);
the artifact store from [teo-devops/minIO-docker](https://github.com/teo-devops/minIO-docker).
