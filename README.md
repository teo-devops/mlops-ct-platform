# mlops-ct-platform

A tool-agnostic MLOps platform that runs a **closed continuous-training loop** on a laptop-sized
Kubernetes cluster (kind), end to end and for real:

```
ingest → validate (gate) → train → evaluate champion/challenger (gate) → register
   → promote (a Git commit) → serve without downtime → monitor drift (PSI) → retrain
```

Every tool sits behind a **contract** — artifact store, model registry, serving, orchestration,
monitoring, model monitoring — and is a self-contained, pinned **module** that can be swapped or
disabled without touching anything else. The example use case, the *Automated Listing Engine*
(ALE: categorise a marketplace listing and flag fraud, inspired by a real hiring case study of a
second-hand marketplace), is a **plugin**: the platform never mentions it.

| What you get | Where |
|---|---|
| GitOps control plane (Argo CD app-of-apps, one AppProject per workload) | `gitops/` — `bootstrap/`, `argo-cd/`, `templates/`, `environments/demo/` |
| Platform modules: cert-manager, KServe, MLflow, Argo Workflows, Prometheus/Grafana, Pushgateway (+ Airflow and Redpanda, opt-in) | `gitops/environments/demo/platform/<module>/` |
| Workload registrations, grouped by owner (`shared/`, `<use-case>/`) | `gitops/environments/demo/{projects,apps}/<group>/` |
| Shared workloads: MinIO with per-consumer users, CT alerting rules and the *CT Loop* dashboard | `workloads/` |
| The step contract: pipeline steps as containers, orchestrator-agnostic | `libs/ctsteps/` |
| Orchestrator adapters (Argo Workflows runs the demo; Airflow exercised as an opt-in module; KFP as reference) | `pipelines/` |
| Platform scripts: cluster lifecycle, bootstrap, operations, repo tooling | `scripts/` |
| kind cluster definition and the images preloaded into it | `cluster/` |
| Platform docs: architecture, contracts, the loop, module cards, decisions, profiles, runbook | `docs/` |
| The example use case: plugin, API, three workloads, **its own docs, scripts and secrets** | `use-cases/automated-listing-engine/` |

## Quickstart (≈15 minutes on a laptop)

Requirements: Docker, kind ≥ 0.31, kubectl, helm ≥ 3.14, python ≥ 3.11 with PyYAML, `gh` logged in
(Argo CD reads the repository anonymously, but the promote step pushes the deployment commit to it,
so on your fork you need a token that can write) — `make prereqs` checks them.

```bash
# platform (scripts/cluster, scripts/platform)
make up          # 02  kind cluster + ingress-nginx + image preload (~5 min)
make secrets     # 03  platform identities and Secrets, then each use case's (random, cluster-only, never in Git)
make bootstrap   # 04  Argo CD from the chart, then root-app: everything else arrives by GitOps
make wait        # 05  platform modules Synced/Healthy
# the use case (use-cases/$USE_CASE/scripts, default automated-listing-engine)
make build       # 06  use-case images -> kind
make pipeline    # 07  first run of the CT pipeline for every model: version 0 -> 1
make smoke       # 08  real request, fallback drill, network-policy probe
make drift       # 09  the world changes -> drift -> retrain -> promote commit -> new version served
# any time
make status      #     Applications, served models, pipelines, URLs and passwords
make down        # 10
```

`make demo` chains 02 → 08; `make prereqs` (01) checks the tools. Every UI answers on
`http://<name>.localhost:8088`. Another use case runs the same flow with `USE_CASE=<name>`.

## UIs and credentials

Every UI is published by ingress-nginx on `http://<name>.localhost:8088` (browsers resolve
`*.localhost` to 127.0.0.1, no `/etc/hosts` needed). `make status` prints this table with the live values.

| UI | URL | User | Password | Notes |
|---|---|---|---|---|
| Argo CD | http://argocd.localhost:8088 | `admin` | `admin-demo` | bcrypt in `gitops/argo-cd/values.yaml` |
| Argo Workflows | http://argo.localhost:8088 | — | — | no auth in the demo (`server.authModes: [server]`) |
| MLflow | http://mlflow.localhost:8088 | — | — | no auth |
| Grafana | http://grafana.localhost:8088 | `admin` | `admin-demo` | *CT Loop* dashboard under folder `mlops-ct-platform` |
| Prometheus | http://prometheus.localhost:8088 | — | — | |
| MinIO console | http://minio.localhost:8088 | `root` | `minio-demo` | buckets `datasets` · `models` · `predictions` · `mlflow` |
| Automated Listing Engine API | http://automated-listing-engine.localhost:8088/docs | — | — | the example use case (OpenAPI UI) |

> **These are demo defaults, deliberately known.** They exist so that a fresh laptop needs no
> lookup; they are never in a Secret in Git (the scripts create them) but they are in this file.
> Change them before the cluster is reachable by anyone else:
> `MINIO_ROOT_PASSWORD=… GRAFANA_ADMIN_PASSWORD=… make secrets` (after deleting the two Secrets, then
> restart `minio` and `kps-grafana`), and for Argo CD a new bcrypt hash in `gitops/argo-cd/values.yaml`
> or `argocd account update-password`. Machine-to-machine keys (artifact-store users, the Git
> token) are random or yours and never printed. Production: SSO and a secret manager
> ([docs/design/secrets.md](docs/design/secrets.md)).

## The platform, in one table

| Contract | Module (pinned) | What a use case gets |
|---|---|---|
| artifact-store | MinIO | S3 buckets `datasets` / `models` / `predictions` and a least-privilege user per consumer |
| model-registry | MLflow | runs, registered models, aliases `champion` / `challenger` / `previous` |
| serving | KServe (Standard mode) | an `InferenceService` per model, pulled by version from the artifact store |
| orchestration | Argo Workflows (Airflow opt-in) | the step contract run as a pipeline, schedules, RBAC for its namespace |
| monitoring | kube-prometheus-stack + Pushgateway | scraping, generic CT alerting rules, the *CT Loop* dashboard |
| model-monitoring | Evidently (`ctsteps drift`) | PSI against the frozen training reference, automatic retrain above threshold |
| event-bus (opt-in) | Redpanda | the prediction records on a Kafka topic: the monitor reads its window from it; Strimzi in production |
| promotion | `ctsteps promote` + Argo CD | deployment = a commit; rollback = another commit |

Modules are self-contained directories under `gitops/environments/demo/platform/`; each has a card
in `docs/modules/` saying what it promises, how to replace it and how to disable it. The parts of the
reference architecture that are not implemented (Kafka, Feast, Katib, Great Expectations, Argo
Rollouts) have cards too, with their contract and where they plug in.

## The example use case: Automated Listing Engine (ALE)

`use-cases/automated-listing-engine/` — categorise a marketplace listing and flag fraud; two models, one API
with graceful degradation, a synthetic data source with a "post-season" drift profile. It is the
use case the `make` targets drive by default (`USE_CASE=automated-listing-engine`), and it proves the loop:

```
$ make drift
drift-categorizer  level=retrain max_psi=0.3285 rows=1205 retrain=ct-categorizer-drift-j7m77
✓ ct-categorizer-drift-j7m77 Succeeded      gate: f1_macro improved by 0.1511 (0.99 vs 0.84)
46e44d1 ct: promote automated-listing-engine/categorizer v2 (trigger=drift)
served versions after: categorizer/fraud = 2 1   (before: 1 1)
```

* **No model is deployed by hand** — only through the pipeline's gates and a promotion commit.
* **Silent failure is caught by distributions**, not by errors: every prediction is logged, the
  monitor compares it with the champion's training reference every 10 minutes.
* **Degradation is a product decision**: the fraud check falls back to explainable rules, the
  listing flow never blocks; the categorizer fails loud.
* **Isolation is declared**: one namespace/AppProject/Application per workload, NetworkPolicies
  shipped by each chart, verified by the smoke test.

A second use case is a new directory with the same shape — see [use-cases/README.md](use-cases/README.md).

## Repository map

```
mlops-ct-platform/
├── README.md · AGENTS.md · Makefile          Makefile = the ordered entry point (make help)
├── gitops/                                   what Argo CD reconciles, and how it is bootstrapped
│   ├── bootstrap/                            root-app (applied once by scripts/platform/04-install.sh)
│   ├── argo-cd/values.yaml                   the engine's single source of configuration
│   ├── templates/                            AppProject + Application templates for new workloads
│   └── environments/
│       ├── demo/                             the environment that runs on kind
│       │   ├── kustomization.yaml · argo-cd.yaml
│       │   ├── platform/<module>/            one directory per platform module: pinned chart + values (+ manifests)
│       │   ├── projects/<group>/             one AppProject per workload   ┐ groups: shared/, <use-case>/
│       │   └── apps/<group>/                 one Application per workload  ┘ (scripts/repo/register-workload.py --group)
│       ├── prod/ · aws/                      documented shapes of the same tree (docs/design/profiles.md)
├── cluster/                                  kind.yaml and the image preload list
├── workloads/                                charts of the shared workloads: minio, observability
├── libs/ctsteps/                             the step contract: python package + `ctsteps` CLI + tests + base image
├── pipelines/                                orchestrator adapters (argo/ notes; adapters/airflow, adapters/kfp as reference)
├── scripts/                                  platform scripts; launch flow numbered 01 → 10 (scripts/README.md)
│   ├── lib.sh                                shared helpers; every path resolves from the repo root
│   ├── cluster/                              01-prereqs · 02-up · 10-down
│   ├── platform/                             03-secrets · 04-install · 05-wait · status · credentials · deploy-local
│   └── repo/                                 validate-coherence.py · register-workload.py · render.sh
├── use-cases/                                one directory per use case (use-cases/README.md = how to add one)
│   └── automated-listing-engine/
│       ├── README.md
│       ├── docs/                             architecture of the instance · case-study · runbook
│       ├── scripts/                          secrets · 06-build-images · 07-run-pipeline · 08-smoke · 09-induce-drift · promote
│       ├── plugin/                           the UseCase implementation + the steps image (FROM ctsteps-base)
│       ├── api/                              FastAPI orchestrator with graceful degradation + tests
│       └── workloads/                        api/ · serving/ · pipelines/ — one Helm chart per workload
└── docs/                                     platform documentation (docs/README.md = reading order)
    ├── design/                               architecture · contracts · ct-loop · profiles · secrets · archetypes
    ├── modules/                              one card per module, implemented and gaps
    ├── operations/                           runbook · what-the-demo-does-not-prove
    └── decisions.md · roadmap.md
```

## Read next

* [docs/design/architecture.md](docs/design/architecture.md) — domains, the synchronous and asynchronous paths, network
* [docs/design/contracts.md](docs/design/contracts.md) — the six contracts and the step CLI
* [docs/design/ct-loop.md](docs/design/ct-loop.md) — the loop step by step, with what each step reads and writes
* [use-cases/README.md](use-cases/README.md) — the shape of a use case and the six steps to add one
* [scripts/README.md](scripts/README.md) — every script, its `make` target and the launch order
* [docs/modules/](docs/modules/) — one card per module, including the gaps (Kafka, Feast, Katib, Great Expectations, Argo Rollouts)
* [docs/decisions.md](docs/decisions.md) — ADRs: why Argo Workflows and not Airflow in kind, sqlite, MinIO, push vs PR…
* [use-cases/automated-listing-engine/docs/](use-cases/automated-listing-engine/docs/) — the example use case: instance architecture, case study, runbook
* [docs/operations/what-the-demo-does-not-prove.md](docs/operations/what-the-demo-does-not-prove.md) — read this before extrapolating

The GitOps control plane is inherited from [teo-devops/Argo-cd-Labs](https://github.com/teo-devops/Argo-cd-Labs);
the artifact store from [teo-devops/minIO-docker](https://github.com/teo-devops/minIO-docker).
