# Decisions (ADR-style, short)

Each entry: context → decision → consequence. Newest last.

### 1. Inherit the GitOps control plane from Argo-cd-Labs instead of designing a new one
The isolation model (`1 workload = 1 namespace = 1 AppProject = 1 Application`), the four-phase
bootstrap, the coherence validator and the templates already existed and run a real cluster.
→ Copied, translated, and extended for a monorepo (every workload reads this repository) and for
platform modules (upstream charts under the `platform` project). → Registering a workload is still
two files and one script; the validator now also checks platform modules.

### 2. Monorepo for the portfolio, one directory per workload
The original model is one repository per workload. A portfolio must be readable in one place.
→ `1 repo` collapses to `1 directory` (`workloads/<name>`, `use-cases/<uc>/workloads/<name>`); the
AppProject still confines each workload to one namespace. → The `sourceRepos` of every AppProject is
the same URL; isolation comes from `destinations` only, which the validator enforces.

### 3. Modules are directories with a contract, not a Helm umbrella chart
Decoupling has to be visible in the tree. → `gitops/environments/demo/platform/<module>/{application,values}`;
disabling a module is deleting a line; contracts are written down in docs/design/contracts.md and the
step CLI. → Some duplication between profiles (`values.yaml` per profile per module) in exchange
for zero coupling between modules.

### 4. Argo Workflows for the demo; Airflow and Kubeflow Pipelines as adapters
The reference stack names Airflow (ETL) and KFP + Katib (training). On kind, Airflow needs a
scheduler, a webserver and a database and KFP needs ~10 pods; Argo Workflows starts in a minute and
is in the same family as the engine. → Steps are containers with a fixed contract; the orchestrator
is a thin adapter (`pipelines/`). → Changing orchestrator rewrites one YAML/DAG, not one step.

### 5. Prediction log on the artifact store instead of Kafka
The asynchronous path of the reference architecture is an event bus. For the demo, JSONL objects
in `s3://predictions` give the drift monitor the same records with one fewer stateful system.
→ `event-bus` is a documented module gap with the same record schema. → No real-time consumers,
window-based monitoring only.

### 6. MLflow with sqlite on a PVC
The chart's Postgres subchart points at frozen `bitnamilegacy` images. → sqlite on a
`Prune=false` PVC, `Recreate` strategy, 2 uvicorn workers. → Single replica; the prod profile uses a
managed Postgres.

### 7. Own MinIO chart pinned on quay.io
MinIO images left Docker Hub in 2025; the community chart is unmaintained. → A 150-line chart
derived from teo-devops/minio-k8s with the bucket/user/policy provisioning of minIO-docker as a
PostSync hook. → Per-consumer least-privilege users (`models-reader`, `pipeline`, `api-writer`,
`mlflow`); root never leaves the `minio` namespace.

### 8. KServe in Standard mode, no Istio, no Knative, cluster-wide S3 defaults
The demo reaches predictors in-cluster; the ingress gateway is what the prod profile adds. → S3
endpoint/region/scheme are set once in the KServe module, so a workload's Secret carries only
credentials and is never declared in Git. → No canary traffic split in the demo (module gap).

### 9. Promotion is a push to `main`, not a pull request
The deployment must be a commit for the audit trail and the rollback story. In the demo the
pipeline pushes directly (rebase-and-retry on conflicts); `CT_PROMOTE_MODE=pr` is the production
mode (a PR that CI validates and auto-merges when the gate passed). → The same bot token as the
Argo CD read credential in the demo; a scoped bot token in production.

### 10. The served version lives in two values files, bumped in one commit
The API reports lineage (`model_version`) and the serving chart pulls the artefact. → `promote` bumps
`models.<model>.version` in both the serving and the API profile values in the same commit: one
commit = one release, predictor and lineage never disagree.

### 11. The data-source state is a ConfigMap outside Git
`make drift` has to change "the world" the use case ingests. Patching a Git-managed ConfigMap would
be reverted by self-heal, committing it would be lying (it is not platform configuration). → Same
treatment as a Secret: created by the bootstrap script, mutated by the demo, documented.

### 12. No Cilium, no Rollouts, no Feast, no Katib, no Great Expectations in the demo
Each would add a controller and a story of its own without changing the control flow being
demonstrated. → Documented as module gaps with their contract and their production counterpart.

### 13. Airflow exercised as an opt-in module, not as the demo orchestrator
The roadmap asked for the Airflow adapter to run on kind, and #4 still holds: Airflow costs an api-server, a
scheduler, a dag-processor and a database for a loop that Argo Workflows runs with one controller. → A complete
module (`platform/airflow/`: chart 1.22.0 on `LocalExecutor`, own Postgres because the subchart is
`bitnamilegacy`, DAGs by git-sync from this repository, keys out of band, no login like the Argo UI) whose line
in the platform kustomization is commented; the DAG mirrors the WorkflowTemplate step by step and was run
end-to-end, promote included. → Enabling it is uncomment + `make secrets` + commit; the drift monitor keeps
submitting Argo Workflows, so Airflow sits next to Argo rather than replacing it (docs/modules/airflow.md).
