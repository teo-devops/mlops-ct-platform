# Instructions for AI assistants working on this repository

You are helping on **mlops-ct-platform**: a tool-agnostic MLOps platform demonstrating a closed
continuous-training loop on kind. Read `docs/design/contracts.md` and `docs/decisions.md` before
proposing changes; most "improvements" that look obvious were decided against, on purpose.

## The model, in one line each

* **Contracts, not tools.** A module lives in `gitops/environments/demo/platform/<module>/` and implements one
  contract. Replacing a tool means a new directory that honours the same contract; never wire two
  modules to each other's internals.
* **Steps are containers.** `libs/ctsteps` is the pipeline; orchestrators are adapters in
  `orchestrators/` that read a use case's pipelines values as data. Do not put use-case logic in a
  step, do not put orchestration in a step, do not name a use case in an adapter.
* **The serving side has a library too.** `libs/ctserve` is what a use-case API owes the platform
  (`uc_*` metrics, `Telemetry.emit`, circuit breaker). Where a prediction record goes (S3 log, event
  bus) is platform configuration (`CT_*` env from the chart), never API code.
* **A use case is a plugin** (`use-cases/<name>/`): a `UseCase` implementation, an API, its workload
  charts, **its own docs, scripts and secrets**. The platform never mentions a use case by name except
  as data: its group under `gitops/environments/demo/{projects,apps}/`, its users/namespaces in the MinIO
  chart values, its pipelines namespace in the orchestration module values, and `USE_CASE ?=` in the
  Makefile. Use-case documentation goes in `use-cases/<name>/docs/`, never in `docs/`; platform scripts
  (`scripts/`) must not hardcode a use case — they use the `mlops-ct-platform.dev/group` label or
  iterate over `use-cases/*/`.
* **GitOps rules inherited from Argo-cd-Labs**: `1 workload = 1 namespace = 1 AppProject =
  1 Application` (= 1 directory here); AppProjects are written by hand and confine a workload to its
  namespace; cluster-scoped things belong to the `platform` project; nothing applied to the cluster
  lives outside `gitops/environments/<env>/`, and that directory never references `../..`.
* **Secrets are never in Git.** No SOPS, no Sealed Secrets — do not propose them unless asked. They
  are created before the first sync by `scripts/platform/03-secrets.sh`. The same goes for the
  `ct-data-source` ConfigMap (state of the outside world).
* **The deployment is a commit.** Models reach serving only through `ctsteps promote` bumping
  `models.<model>.version` in the profile values of the serving and API charts. Do not add
  `kubectl patch`, `ignoreDifferences` on `storageUri`, or any other way to deploy that bypasses Git.
* **Versions are pinned, never ranges.** Charts, images (MinIO by tag on quay.io), Python packages
  (the scikit-learn/numpy/joblib pins are those of `kserve/sklearnserver:v0.20.0` — a model pickled
  by the steps must load there).

## Things that are deliberate

* Argo Workflows in the demo, Airflow/KFP as reference adapters (docs/decisions.md #4).
* Prediction log on S3 instead of Kafka; sqlite for MLflow; own MinIO chart; KServe Standard mode
  without Istio; push to `main` instead of a PR for promotion; the observability *workload* holds
  rules and dashboards while the monitoring *module* holds the stack.
* `autoscalerClass: external` on kind; `startupapicheck` off; Alertmanager off; Dex off.
* Module gaps (event-bus, feature-store, data-quality, hpo, progressive-delivery) have cards in
  `docs/modules/`. Implementing one = a new module directory + a card, not a rewrite.

## Before you finish a change

`make validate` (coherence validator, kustomize, helm lint, ruff, pytest) must pass. If you change
a chart, `scripts/repo/render.sh rendered` shows what Argo CD would apply. If you change a step, the
tests in `libs/ctsteps/tests` cover the whole pipeline against a fake S3 and a local MLflow — extend
them. Never commit models, datasets or `.venv*`.
