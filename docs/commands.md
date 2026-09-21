# Command reference

Everything is `make <command>` from the repository root; `make` lists them. Commands act on the
cluster `ct` (kind) and, when it matters, on the use case `USE_CASE=<name>` (default
`automated-listing-engine`). Variables go before or after the command: `USE_CASE=x make smoke`.

## Start here

| Command | What it does | Notes |
|---|---|---|
| `make prereqs` | checks tools (docker, kind, kubectl, helm, python, git, gh), the GitHub credential, that WARP is off, that host port 8088 is free, that the Docker builder resolves DNS, memory; prints what the demo will deploy | fails with the fix for each ✗; `SKIP_BUILD_CHECK=1` skips the builder probe |
| `make demo` | the whole thing: `up` → `secrets` → `bootstrap` → `wait` → `build` → `pipeline` → `smoke` → `status` | ≈15 min; `USE_CASE=<uc>` to demo another deployed use case |
| `make drift` | the closed loop for one use case: flips its data source to the drift profile, sends traffic from that world, runs the monitor, waits for the retrains, shows the promotion commits and the new served versions | `REQUESTS=600` |
| `make status` | Applications (with owner group), served models and versions, last pipelines, UIs and passwords | any time |
| `make down` | deletes the kind cluster | the repository keeps nothing of the cluster |

## Operate a use case (`USE_CASE=<name>`)

| Command | What it does | Notes |
|---|---|---|
| `make pipeline` | submits `ct-pipeline` for every model and waits; prints the gate decision and the promotion | `MODELS="a b"`, `TRIGGER=`, `PROFILE=` |
| `make promote MODEL=<m> VERSION=<n>` | promotes a registry version: alias `champion` + one commit bumping the served version | rollback = promote the previous |
| `make rollback MODEL=<m>` | promotes the version under the alias `previous` — no number to look up | |
| `make smoke` | sample request from `usecase.yaml`, lineage check, served versions from the metrics, fallback drill (if the use case declares a degradable model), network-policy probe | |
| `make build` | builds `<uc>-steps` (plugin) and `<uc>-api` and loads them into kind | rebuild after changing the plugin or the API; the API needs a rollout restart |

Every one of these refuses a use case the demo does not deploy and tells you how to deploy it.

## Shape the demo

| Command | What it does | Notes |
|---|---|---|
| `make module` | which platform modules are on and which are opt-in | |
| `make module ENABLE=<m>` | uncomments the module in the platform kustomization, preloads its images into kind, creates its out-of-band state, runs its enable hook, validates | `COMMIT=1` commits and pushes — Argo CD deploys what `main` says |
| `make module DISABLE=<m>` | comments it and runs its disable hook (Argo Rollouts cleans the Service selectors it leaves) | `COMMIT=1` |
| `make use-case` | which use cases the demo deploys | |
| `make use-case ENABLE=<uc>` | lists its group in `apps/` and `projects/`, creates its namespaces and credentials on the cluster, validates | `COMMIT=1`; Argo CD creates its three workloads |
| `make use-case DISABLE=<uc>` | unlists it: Argo CD prunes its workloads; its namespaces and Secrets stay for the next enable | `COMMIT=1` |
| `make new-use-case NAME=<uc> MODELS=a,b` | renders `scripts/repo/use-case-template/` into `use-cases/<uc>/` and registers it everywhere the platform keeps data about use cases; the result runs as it is | `TASK=classification\|regression`, `API=false` for a use case that only exposes models |

Opt-in modules: `airflow` (orchestrator, DAG factory over the use cases), `redpanda` (event bus for
the prediction records), `argo-rollouts` (canary of a use case's API judged by the SLO analysis).
Their cards in [modules/](modules/README.md) say what else to flip in the use case's values.

## Step by step (what `make demo` runs)

| Step | Command | What it does |
|---|---|---|
| 01 | `make prereqs` | see above |
| 02 | `make up` | kind cluster from `cluster/kind.yaml`, ingress-nginx on host port 8088, images of the **enabled** modules preloaded |
| 03 | `make secrets` | platform namespaces and Secrets (MinIO root and one key per artifact-store user, MLflow, Grafana), then each **deployed** use case's (namespaces, its own S3 users, Git credential for promote, data-source ConfigMap) — never in Git |
| 04 | `make bootstrap` | Argo CD from the pinned chart with the same values it will later manage itself, AppProjects, root-app; from here on every change is a commit |
| 05 | `make wait` | until every platform module is Synced/Healthy (`SCOPE=<uc>` for a use case) |
| 06–08 | `make build pipeline smoke` | the use case: images, first training (v0 → v1), smoke |
| 09 | `make drift` | the closed loop |
| 10 | `make down` | delete |

## Repository

| Command | What it does |
|---|---|
| `make validate` | coherence validator (GitOps tree, platform modules, use cases and their isolation, chart templates equal to the platform's), kustomize renders, helm lint of every chart, ruff, pytest of every library and use case |
| `make venv` | `.venv-dev` with every python package in dev mode (needed by `validate`) |
| `make render` | what Argo CD would apply, rendered under `rendered/` |

## Variables

| Variable | Default | Used by |
|---|---|---|
| `USE_CASE` | `automated-listing-engine` | every use-case command |
| `CLUSTER` | `ct` | cluster and context (`kind-ct`) |
| `MODEL`, `VERSION`, `TRIGGER` | — | `promote`, `rollback` |
| `MODELS`, `PROFILE`, `REQUESTS` | from `usecase.yaml` | `pipeline`, `drift` |
| `ENABLE`, `DISABLE`, `COMMIT` | — | `module`, `use-case` |
| `NAME`, `MODELS`, `TASK`, `API` | — | `new-use-case` |
| `GIT_USER`, `GIT_TOKEN` | `teo-devops`, `gh auth token` | `secrets`, `bootstrap` (promote push; a private fork's Argo CD) |
| `MINIO_ROOT_PASSWORD`, `GRAFANA_ADMIN_PASSWORD` | `minio-demo`, `admin-demo` | `secrets` |
| `DOCKER_BUILD_HOST_NETWORK` | `1` | `build`, `prereqs` (builders without DNS) |
| `SCOPE`, `TIMEOUT` | `platform`, `1200` | `wait` |
