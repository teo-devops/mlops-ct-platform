# mlops-ct-platform

A tool-agnostic MLOps platform that runs a **closed continuous-training loop** on a laptop-sized
Kubernetes cluster (kind), end to end and for real:

```
ingest → validate (gate) → train → evaluate champion/challenger (gate) → register
   → promote (a Git commit) → serve without downtime → monitor drift (PSI) → retrain
```

Every tool sits behind a **contract** and is a pinned, swappable **module**. A use case is a
**plugin** the platform never mentions: it brings its data, models and API; the platform brings the
pipeline, the gates, the registry, the serving, the monitoring and the promotion. Each use case has
its own demo, namespaces, buckets and credentials, and cannot see the others.

## Quick start

You need Docker, kind ≥ 0.31, kubectl, helm ≥ 3.14, python ≥ 3.11 (with PyYAML) and `gh` logged in
(the promote step pushes a commit). ~8 GiB of RAM free. `make prereqs` checks all of it.

```bash
make prereqs        # tools, credentials, network, memory — and what will be deployed
make demo           # kind cluster → platform → one use case → smoke test   (≈15 min)
```

`make demo` runs **one use case** — by default the first one the demo deploys; pick another with
`make demo USE_CASE=<name>`. When it finishes it prints `make status`: every UI, the served models,
the passwords. Then play:

| Try | How |
|---|---|
| send a request to the model API | the use case's README has the `curl` — [pick one below](#use-cases) |
| watch the pipeline that trained it | http://argo.localhost:8088 — one Workflow per model, seven steps |
| see the gate decision and the registry | http://mlflow.localhost:8088 — experiment `<use-case>/<model>`, aliases `champion` / `previous` |
| see what a promotion changed | http://argocd.localhost:8088 (`admin` / `admin-demo`) — the serving and API Applications, synced from a commit |
| **close the loop** | `make drift` — the world changes, the monitor detects it, retrains, promotes, the new version is served |
| watch it on a dashboard | http://grafana.localhost:8088 (`admin` / `admin-demo`) — *CT Loop*: PSI, retrains, served versions |
| roll back | `make rollback MODEL=<m>` — one commit, the previous champion is back |
| break a model | the use case's README says which one degrades gracefully and which one fails loud |
| finish | `make down` |

`make` lists every command; [docs/commands.md](docs/commands.md) explains each one;
[docs/getting-started.md](docs/getting-started.md) has the three ways in (see it run · bring your
use case · operate the platform). Every UI answers on `http://<name>.localhost:8088` — no `/etc/hosts`.

## Use cases

Every use case's README has the same shape — **Quick start · Play · Models · Layout** — so from
either README you can bring it up and play.

| Use case | What | Demo |
|---|---|---|
| [automated-listing-engine](use-cases/automated-listing-engine/README.md) | categorise a second-hand listing and flag fraud — two classifiers behind one API, rules fallback for the fraud model | deployed by default |
| [delivery-eta](use-cases/delivery-eta/README.md) | minutes from order to door — one regressor, no fallback; generated with the scaffold | opt-in: `make use-case ENABLE=delivery-eta COMMIT=1` |

Bring your own in one command — it renders the plugin, the API, the three charts and the docs,
registers everything, and runs as it is until you fill in the data and the model:

```bash
make new-use-case NAME=churn MODELS=risk TASK=classification     # then: use-cases/README.md
```

## Shape the demo

The demo deploys **the core** (GitOps engine, KServe, MLflow, Argo Workflows, Prometheus/Grafana,
MinIO, the CT rules) plus the **use cases** and **opt-in modules** that are listed. Nothing that is
off is preloaded, secreted or synced. Argo CD deploys what `main` says, so enabling is a commit
(`COMMIT=1` does it for you).

```bash
make module                            # platform modules: on / opt-in (Airflow, Redpanda, Argo Rollouts)
make module ENABLE=airflow COMMIT=1
make use-case                          # use cases the demo deploys
make use-case ENABLE=delivery-eta COMMIT=1
```

## How it works

| Contract | Module (pinned) | What a use case gets |
|---|---|---|
| artifact-store | MinIO | its own buckets `<uc>-datasets` / `<uc>-models` / `<uc>-predictions` and least-privilege users |
| model-registry | MLflow | runs, registered models, aliases `champion` / `challenger` / `previous` |
| serving | KServe (Standard mode) | an `InferenceService` per model, pulled by version from the artifact store |
| orchestration | Argo Workflows (Airflow opt-in) | the step contract run as a pipeline, schedules, RBAC for its namespace |
| monitoring | kube-prometheus-stack + Pushgateway | scraping, generic CT alerting rules, the *CT Loop* dashboard |
| model-monitoring | Evidently (`ctsteps drift`) | PSI against the frozen training reference, automatic retrain above threshold |
| promotion | `ctsteps promote` + Argo CD | deployment = a commit; rollback = another commit |
| progressive-delivery (opt-in) | Argo Rollouts | canary of the use case's API judged by the SLO analysis |
| event-bus (opt-in) | Redpanda | the prediction records on a Kafka topic; the monitor reads its window from it |

Modules are self-contained directories under `gitops/environments/demo/platform/`, each with a card
in [docs/modules/](docs/modules/README.md) (what it promises, pinned version, how to replace or
disable it). The loop step by step: [docs/design/ct-loop.md](docs/design/ct-loop.md); the
architecture: [docs/design/architecture.md](docs/design/architecture.md); why it is like this:
[docs/decisions.md](docs/decisions.md).

### UIs and credentials

| UI | URL | User / password |
|---|---|---|
| Argo CD | http://argocd.localhost:8088 | `admin` / `admin-demo` |
| Argo Workflows | http://argo.localhost:8088 | none |
| MLflow | http://mlflow.localhost:8088 | none |
| Grafana | http://grafana.localhost:8088 | `admin` / `admin-demo` |
| Prometheus | http://prometheus.localhost:8088 | none |
| MinIO console | http://minio.localhost:8088 | `root` / `minio-demo` |
| a use case's API | http://<use-case>.localhost:8088/docs | none |

> Demo defaults, deliberately known so that a fresh laptop needs no lookup. Change them before the
> cluster is reachable by anyone else: `MINIO_ROOT_PASSWORD=… GRAFANA_ADMIN_PASSWORD=… make secrets`
> (after deleting the two Secrets), a new bcrypt in `gitops/argo-cd/values.yaml` for Argo CD.
> Machine-to-machine keys are random and never printed ([docs/design/secrets.md](docs/design/secrets.md)).

## Repository map

```
mlops-ct-platform/
├── README.md · AGENTS.md · Makefile          Makefile = the entry point (make help)
├── gitops/                                   what Argo CD reconciles, and how it is bootstrapped
│   ├── bootstrap/                            root-app (applied once by scripts/platform/04-install.sh)
│   ├── argo-cd/values.yaml                   the engine's single source of configuration
│   ├── templates/                            AppProject + Application templates for new workloads
│   └── environments/
│       ├── demo/                             the environment that runs on kind
│       │   ├── platform/<module>/            one directory per platform module: pinned chart + values (+ manifests, hooks)
│       │   ├── projects/<group>/             one AppProject per workload   ┐ groups: shared/, <use-case>/
│       │   └── apps/<group>/                 one Application per workload  ┘ (commented group = opt-in)
│       ├── prod/ · aws/                      documented shapes of the same tree (docs/design/profiles.md)
├── cluster/                                  kind.yaml and the image preload list (grouped by module)
├── workloads/                                charts of the shared workloads: minio, observability
├── libs/
│   ├── ctsteps/                              the step contract: python package + `ctsteps` CLI + tests + base image
│   └── ctserve/                              the serving-side contract for use-case APIs (Telemetry, metrics, KServe client)
├── orchestrators/                            orchestrator adapters: argo/ (notes) · airflow/ (DAG factory) · kfp/ (reference)
├── scripts/                                  launch flow 01 → 10 and tooling (scripts/README.md)
│   ├── cluster/                              01-prereqs · 02-up · 10-down
│   ├── platform/                             03-secrets · 04-install · 05-wait · status · module
│   ├── use-case/                             the flow of one use case: secrets · 06-build · 07-pipeline · 08-smoke · 09-drift · promote · rollback · toggle
│   └── repo/                                 validate-coherence.py · register-workload.py · new-use-case.py (+ use-case-template/) · render.sh
├── use-cases/                                one directory per use case (use-cases/README.md)
│   └── <name>/                               usecase.yaml · README · docs/ · plugin/ · api/ · workloads/{api,serving,pipelines}
└── docs/                                     getting-started · commands · design/ · modules/ · operations/ · decisions · roadmap
```

## Read next

* [docs/getting-started.md](docs/getting-started.md) — three ways in · [docs/commands.md](docs/commands.md) — every command
* [use-cases/README.md](use-cases/README.md) — the shape of a use case, the scaffold, isolation
* [docs/design/](docs/README.md) — architecture, contracts, the loop, profiles, secrets
* [docs/modules/](docs/modules/README.md) — one card per module, implemented and gaps
* [docs/decisions.md](docs/decisions.md) — ADRs · [docs/operations/runbook.md](docs/operations/runbook.md) — symptom → cause → fix
* [docs/operations/what-the-demo-does-not-prove.md](docs/operations/what-the-demo-does-not-prove.md) — read before extrapolating

The GitOps control plane is inherited from [teo-devops/Argo-cd-Labs](https://github.com/teo-devops/Argo-cd-Labs);
the artifact store from [teo-devops/minIO-docker](https://github.com/teo-devops/minIO-docker).
