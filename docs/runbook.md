# Runbook

| I want to… | Do |
|---|---|
| see everything | `make status` |
| find a password | `make status` (Argo CD, Grafana, MinIO); Argo Workflows has no auth in the demo |
| retrain now | `make pipeline` (both models) or `MODELS=fraud TRIGGER=manual make pipeline` |
| promote / roll back | `make promote MODEL=fraud VERSION=1` — a commit; Argo CD syncs it in ≤ 3 min (`kubectl -n argocd annotate application listing-engine-serving argocd.argoproj.io/refresh=normal` to hurry) |
| see the gate decision | MLflow → experiment `listing-engine/<model>` → run tags `gate.*`; or the `evaluate` node outputs in Argo Workflows |
| see drift | Grafana → *CT Loop*; Prometheus `ct_drift_psi` |
| reset the world after `make drift` | `kubectl -n listing-engine-pipelines create configmap ct-data-source --from-literal=profile= --dry-run=client -o yaml \| kubectl apply -f -` |
| iterate on a chart without committing | `scripts/25-deploy-local.sh` on a cluster **without** Argo CD (`make up secrets`, skip `bootstrap`) |
| rebuild the API or the steps image | `make build`, then `kubectl -n listing-engine-api rollout restart deploy/listing-engine-api` / next pipeline run picks the new image |
| rotate a secret | delete it, `make secrets`, restart the consumer; for the Git credential also `scripts/credentials.sh add` |
| add a use case | implement `UseCase`, build an image `FROM ctsteps-base`, copy the three workload charts, `python3 scripts/register-workload.py <name> <path> --group <use-case>` ×3, add its namespace to `controller.workflowNamespaces` of the argo-workflows module, create its Secrets |
| disable a module | remove its line from `gitops/environments/demo/platform/kustomization.yaml` (prune deletes it) |

## Things that look like failures and are not

* `listing-engine-serving` **Progressing** right after bootstrap: version 0 has no artefact; the
  first `make pipeline` promotes v1.
* A pipeline whose `register`/`promote` steps are **skipped**: the gate refused (candidate did not
  beat the champion). Expected when the data did not change.
* `ct-drift` reporting `skipped: N rows < 200`: not enough traffic in the window.

## Things that are failures

* `root-app` OutOfSync with `failed to list refs`: the Git credential is missing or expired →
  `scripts/credentials.sh add`.
* An InferenceService stuck with `storage-initializer` errors other than "No model found":
  check `models-s3-credentials` and the MinIO `models-reader` policy (`kubectl -n minio logs job/minio-setup`).
* `promote` failing with `could not push`: the token cannot write to the repository.
