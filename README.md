# mlops-ct-platform

A tool-agnostic MLOps platform that demonstrates a **closed continuous-training loop** on a
laptop-sized Kubernetes cluster (kind):

> ingest → validate (gate) → train → evaluate champion/challenger (gate) → register → promote (GitOps)
> → serve without downtime → monitor drift → retrain automatically.

Every tool is a **module behind a contract** (artifact store, model registry, serving, orchestration,
monitoring, model monitoring) so it can be swapped or disabled without touching the rest. The
*Listing Engine* use case (categorise a marketplace listing and flag fraud, inspired by a real
case study) is a plugin under `use-cases/`; the platform itself never mentions it.

> Work in progress — see `docs/` as it fills up. Quickstart: `make demo`.

## Layout

| Directory | What |
|---|---|
| `bootstrap/`, `config/argo-cd/`, `overlays/demo/` | The GitOps control plane (Argo CD app-of-apps), inherited from [Argo-cd-Labs](https://github.com/teo-devops/Argo-cd-Labs) |
| `overlays/demo/platform/<module>/` | One self-contained directory per platform module: pinned upstream chart + demo values |
| `workloads/` | Shared platform workloads (artifact store, alerting rules) — `1 workload = 1 namespace = 1 AppProject = 1 Application` |
| `libs/ctsteps/` | The step contract: pipeline steps as containers, orchestrator-agnostic |
| `pipelines/` | Orchestrator adapters (Argo Workflows runs the demo; Airflow/KFP as reference) |
| `use-cases/listing-engine/` | The example use case: plugin, API, and its three workloads |
| `scripts/`, `Makefile`, `lab/` | Reproducible bootstrap on kind |
