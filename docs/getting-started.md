# Getting started

Three ways in. Pick yours; every command is `make <something>` from the repository root and
`make` alone lists them. Every UI answers on `http://<name>.localhost:8088`.

## 1. I want to see the loop run (15 minutes)

The README's *Quick start* is this section in short; the use case's README (*Play*) has the requests.

```bash
make prereqs     # tools, credentials, network, memory — and what the demo will deploy
make demo        # kind cluster → platform → example use case → smoke test → status
make drift       # the world changes → drift detected → retrain → promotion commit → new version served
```

What you get: a kind cluster `ct` with the platform (Argo CD, KServe, MLflow, Argo Workflows,
Prometheus/Grafana, MinIO) and **one use case** — the first the demo deploys (`make use-case` lists them;
`make demo USE_CASE=<name>` picks another). Each use case has its own demo, README and runbook. `make status` prints the UIs and passwords; the ones worth opening first:

| | |
|---|---|
| http://argocd.localhost:8088 (`admin` / `admin-demo`) | every workload as an Application, what a promotion changes |
| http://argo.localhost:8088 | the pipeline runs, step by step |
| http://mlflow.localhost:8088 | runs, gate decisions, registered models and their `champion` / `previous` aliases |
| http://grafana.localhost:8088 (`admin` / `admin-demo`) | the *CT Loop* dashboard: PSI, retrains, served versions |

Done: `make down`.

If `make prereqs` marks something ✗ it says what to do (disconnect WARP, free port 8088, …). If
something waits too long, `make status` shows which Application is not Healthy and
[operations/runbook.md](operations/runbook.md) has the symptom → cause table.

## 2. I want to bring my own use case (an afternoon)

```bash
make new-use-case NAME=churn MODELS=risk TASK=classification   # renders and registers use-cases/churn/
```

The generated use case **already works** (synthetic data, tests green, one command to run it). Then:

1. `use-cases/churn/plugin/src/churn/data.py` — the real ingest; `usecase.py` — the four methods
   (`ingest`, `schema`, `build_model`, `evaluate`) with scikit-learn built-ins.
2. `use-cases/churn/api/app/schemas.py` — the real request; `usecase.yaml` `api.sample` to match.
3. `make venv && make validate` — your plugin runs on the platform's step harness, your API on its test client.
4. `make use-case ENABLE=churn COMMIT=1` — deploy it (namespaces, its own credentials, three workloads).
5. `USE_CASE=churn make build pipeline smoke drift`.

Your use case is isolated: its namespaces, its buckets and artifact-store users, its network policies.
It cannot read another use case's models and nothing in it names another one — the validator refuses
otherwise. Details: [../use-cases/README.md](../use-cases/README.md).

## 3. I want to operate or extend the platform

```bash
make module                          # which platform modules are on, which are opt-in
make module ENABLE=airflow COMMIT=1  # Airflow, Redpanda (event bus), Argo Rollouts (canaries)
make use-case                        # which use cases the demo deploys
USE_CASE=<uc> make rollback MODEL=<m>   # back to the previous champion, one command
```

Read in this order: [design/architecture.md](design/architecture.md) (the two paths), [design/contracts.md](design/contracts.md)
(what a module promises), [modules/](modules/README.md) (one card per module: pinned version, how to
replace it), [decisions.md](decisions.md) (why it is like this). Operating: [operations/runbook.md](operations/runbook.md).
The full command reference: [commands.md](commands.md).
