# Runbook (platform)

Use-case specific commands live with the use case (e.g.
[use-cases/listing-engine/docs/runbook.md](../../use-cases/listing-engine/docs/runbook.md)).
`make` targets that operate a use case take `USE_CASE=<name>` (default `listing-engine`).

| I want to… | Do |
|---|---|
| see everything | `make status` (Applications with their owner group, every served model, every pipeline, URLs, passwords) |
| wait for the platform / for one use case | `make wait` / `SCOPE=<use-case> make wait` |
| retrain, promote, roll back, smoke, drift for a use case | `make pipeline` · `make promote MODEL=<m> VERSION=<n>` · `make smoke` · `make drift` (with `USE_CASE=`) |
| hurry an Argo CD sync | `kubectl -n argocd annotate application <app> argocd.argoproj.io/refresh=normal --overwrite` |
| iterate on a chart without committing | `scripts/platform/deploy-local.sh` on a cluster **without** Argo CD (`make up secrets`, skip `bootstrap`) |
| rotate a platform secret | delete it, `make secrets` (with `MINIO_ROOT_PASSWORD=` / `GRAFANA_ADMIN_PASSWORD=` for the human-facing ones), restart the consumer (`minio`, `kps-grafana`), re-sync `minio` so the provisioning hook runs with the new root; Git credential: `scripts/platform/credentials.sh add`; Argo CD admin: new bcrypt in `gitops/argo-cd/values.yaml` |
| register a workload | `python3 scripts/repo/register-workload.py <name> <path> --group <shared\|use-case>` — then READ the AppProject |
| add a use case | [use-cases/README.md](../../use-cases/README.md) |
| add / replace / disable a platform module | a directory under `gitops/environments/demo/platform/` + its card in `docs/modules/`; disable = remove its line from `platform/kustomization.yaml` |
| see what Argo CD would apply | `make render` |

## Things that look like failures and are not

* A use case's serving Application **Progressing** right after bootstrap: version 0 has no
  artefact; the first pipeline run promotes v1.
* A pipeline whose `register`/`promote` steps are **skipped**: the gate refused (the candidate did
  not beat the champion). Expected when the data did not change.
* `ct-drift` reporting `skipped: N rows < min`: not enough traffic in the window.
* Workflows shown as orphans of a pipelines AppProject: runtime objects, by design (archetype `pipeline`).

## Things that are failures

* `root-app` OutOfSync with `failed to list refs`: the Git credential is missing or expired →
  `scripts/platform/credentials.sh add`.
* An InferenceService stuck with `storage-initializer` errors other than "No model found": check
  the consumer's S3 Secret and the MinIO policy of its user (`kubectl -n minio logs job/minio-setup`).
* `promote` failing with `could not push`: the token cannot write to the repository.
* A platform Application Degraded after a change: `make render` and compare; `make lint` catches
  most tree-level mistakes before they reach the cluster.
