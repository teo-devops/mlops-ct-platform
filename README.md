# mlops-ct-platform

A tool-agnostic MLOps platform that runs a **closed continuous-training loop** on a laptop-sized
Kubernetes cluster (kind), end to end and for real:

```
ingest → validate (gate) → train → evaluate champion/challenger (gate) → register
   → promote (a Git commit) → serve without downtime → monitor drift (PSI) → retrain
```

Every tool sits behind a **contract** — artifact store, model registry, serving, orchestration,
monitoring, model monitoring — and is a self-contained, pinned **module** that can be swapped or
disabled without touching anything else. A use case is a **plugin** the platform never mentions:
each one has its own demo (`make demo USE_CASE=<name>`), its own namespaces, buckets and
credentials, and cannot see the others. Two ship with the repository ([use-cases/](use-cases/README.md)).

| What you get | Where |
|---|---|
| GitOps control plane (Argo CD app-of-apps, one AppProject per workload) | `gitops/` — `bootstrap/`, `argo-cd/`, `templates/`, `environments/demo/` |
| Platform modules: cert-manager, KServe, MLflow, Argo Workflows, Prometheus/Grafana, Pushgateway (+ Airflow, Redpanda and Argo Rollouts, opt-in) | `gitops/environments/demo/platform/<module>/` |
| Workload registrations, grouped by owner (`shared/`, `<use-case>/`) | `gitops/environments/demo/{projects,apps}/<group>/` |
| Shared workloads: MinIO with per-consumer users, CT alerting rules and the *CT Loop* dashboard | `workloads/` |
| The step contract: pipeline steps as containers, orchestrator-agnostic | `libs/ctsteps/` |
| The serving-side contract for use-case APIs: `uc_*` metrics, prediction log, event bus, circuit breaker | `libs/ctserve/` |
| Orchestrator adapters (Argo Workflows runs the demo; Airflow exercised as an opt-in module; KFP as reference) | `orchestrators/` |
| Platform scripts: cluster lifecycle, bootstrap, operations, repo tooling | `scripts/` |
| kind cluster definition and the images preloaded into it | `cluster/` |
| Platform docs: architecture, contracts, the loop, module cards, decisions, profiles, runbook | `docs/` |
| The use cases: `usecase.yaml`, plugin, API, three charts, docs — isolated from each other; `make new-use-case` scaffolds one | `use-cases/<name>/` |

## Start

```bash
make prereqs   # tools, credentials, network, memory — and what the demo will deploy
make demo      # cluster → platform → one use case → smoke → status   (≈15 min, ~8 GiB)
make drift     # the world changes → drift → retrain → promotion commit → new version served
make down
```

There is **one demo per use case**: `make demo USE_CASE=<name>` (default: the first use case the
demo deploys — `make use-case` lists them). The platform is shared; each use case's loop, data and
namespaces are its own.

`make` lists every command; **[docs/getting-started.md](docs/getting-started.md)** has the three
ways in (see the loop · bring your use case · operate the platform) and
**[docs/commands.md](docs/commands.md)** the reference. Requirements: Docker, kind ≥ 0.31, kubectl,
helm ≥ 3.14, python ≥ 3.11 with PyYAML, `gh` logged in (the promote step pushes the deployment commit).

The demo deploys **the core** plus the **use cases** and **opt-in modules** listed in
`gitops/environments/demo/` — nothing that is off is preloaded, secreted or synced. Argo CD deploys
what `main` says, so enabling is a commit (`COMMIT=1` does it):

```bash
make module                          # Airflow, Redpanda, Argo Rollouts: opt-in, off by default
make module ENABLE=airflow COMMIT=1
make use-case                        # which use cases the demo deploys (one is on, the other opt-in)
make use-case ENABLE=delivery-eta COMMIT=1 && USE_CASE=delivery-eta make build pipeline smoke drift
make new-use-case NAME=churn MODELS=risk   # your own: rendered, registered, working
```

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
| a use case's API | http://<use-case>.localhost:8088/docs | — | — | one per deployed use case (OpenAPI UI) |

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
| progressive-delivery (opt-in) | Argo Rollouts | canary of a use-case API judged by the SLO analysis; the model itself still switches by rolling update on kind |
| event-bus (opt-in) | Redpanda | the prediction records on a Kafka topic: the monitor reads its window from it; Strimzi in production |
| promotion | `ctsteps promote` + Argo CD | deployment = a commit; rollback = another commit |

Modules are self-contained directories under `gitops/environments/demo/platform/`; each has a card
in `docs/modules/` saying what it promises, how to replace it and how to disable it. The parts of the
reference architecture that are not implemented (Kafka, Feast, Katib, Great Expectations, Argo
Rollouts) have cards too, with their contract and where they plug in.

## Use cases

| Use case | What | In the demo |
|---|---|---|
| [automated-listing-engine](use-cases/automated-listing-engine/README.md) | categorise a marketplace listing and flag fraud — two classifiers, one API with rules fallback; inspired by a hiring case study of a second-hand marketplace | deployed |
| [delivery-eta](use-cases/delivery-eta/README.md) | minutes from order to door — one regressor, no fallback; generated with `make new-use-case` | opt-in |

Each has its own README, docs, runbook and demo (`make demo USE_CASE=<name>`); what every use case
proves — no model deployed by hand, silent failure caught by distributions, isolation declared and
verified — is in [use-cases/README.md](use-cases/README.md).

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
├── libs/
│   ├── ctsteps/                              the step contract: python package + `ctsteps` CLI + tests + base image
│   └── ctserve/                              the serving-side contract for use-case APIs (Telemetry, metrics, breaker) + base image
├── orchestrators/                            orchestrator adapters: argo/ (notes) · airflow/ (DAG factory, exercised) · kfp/ (reference)
├── scripts/                                  platform scripts; launch flow numbered 01 → 10 (scripts/README.md)
│   ├── lib.sh                                shared helpers; every path resolves from the repo root
│   ├── cluster/                              01-prereqs · 02-up · 10-down
│   ├── platform/                             03-secrets · 04-install (+ credential) · 05-wait · status
│   ├── use-case/                             the flow of one use case: secrets · 06-build · 07-pipeline · 08-smoke · 09-drift · promote
│   └── repo/                                 validate-coherence.py · register-workload.py · new-use-case.py (+ use-case-template/) · render.sh
├── use-cases/                                one directory per use case (use-cases/README.md = how to add one)
│   └── <name>/                               one per use case, same shape (two ship: automated-listing-engine, delivery-eta)
│       ├── usecase.yaml                      what the platform's flow scripts need (models, API, drift profile)
│       ├── README.md
│       ├── docs/                             architecture of the instance · runbook (· case study)
│       ├── plugin/                           the UseCase implementation + the steps image (FROM ctsteps-base)
│       ├── api/                              FastAPI: fan-out, fallback rules, schemas (telemetry/metrics from libs/ctserve) + tests
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
* [use-cases/README.md](use-cases/README.md) — the shape of a use case, `make new-use-case`, isolation
* [scripts/README.md](scripts/README.md) — every script, its `make` target and the launch order
* [docs/modules/](docs/modules/) — one card per module, including the gaps (Kafka, Feast, Katib, Great Expectations, Argo Rollouts)
* [docs/decisions.md](docs/decisions.md) — ADRs: why Argo Workflows and not Airflow in kind, sqlite, MinIO, push vs PR…
* [docs/operations/what-the-demo-does-not-prove.md](docs/operations/what-the-demo-does-not-prove.md) — read this before extrapolating

The GitOps control plane is inherited from [teo-devops/Argo-cd-Labs](https://github.com/teo-devops/Argo-cd-Labs);
the artifact store from [teo-devops/minIO-docker](https://github.com/teo-devops/minIO-docker).
