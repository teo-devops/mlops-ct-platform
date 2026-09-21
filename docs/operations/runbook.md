# Runbook (platform)

What is specific to a use case lives with the use case (`use-cases/<name>/docs/runbook.md`).
`make` targets that operate a use case take `USE_CASE=<name>` (default: the first use case the demo
deploys — `make use-case` lists them).

| I want to… | Do |
|---|---|
| see everything | `make status` (Applications with their owner group, every served model, every pipeline, URLs, passwords) |
| wait for the platform / for one use case | `make wait` / `SCOPE=<use-case> make wait` |
| retrain, promote, roll back, smoke, drift for a use case | `make pipeline` · `make promote MODEL=<m> VERSION=<n>` · `make smoke` · `make drift` (with `USE_CASE=`) |
| hurry an Argo CD sync | `kubectl -n argocd annotate application <app> argocd.argoproj.io/refresh=normal --overwrite` |
| see what Argo CD would apply before committing | `make render` (`scripts/repo/render.sh`) |
| rotate a platform secret | delete it, `make secrets` (with `MINIO_ROOT_PASSWORD=` / `GRAFANA_ADMIN_PASSWORD=` for the human-facing ones), restart the consumer (`minio`, `kps-grafana`), re-sync `minio` so the provisioning hook runs with the new root; Git credential: `scripts/platform/04-install.sh credential add`; Argo CD admin: new bcrypt in `gitops/argo-cd/values.yaml` |
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

* `root-app` OutOfSync with `failed to list refs`: on a private fork the Git credential is missing
  or expired → `scripts/platform/04-install.sh credential add`.
* An InferenceService stuck with `storage-initializer` errors other than "No model found": check
  the consumer's S3 Secret and the MinIO policy of its user (`kubectl -n minio logs job/minio-setup`).
* `promote` failing with `could not push`: the token cannot write to the repository.
* A platform Application Degraded after a change: `make render` and compare; `make lint` catches
  most tree-level mistakes before they reach the cluster.

## Symptom → cause → fix

| Symptom | Cause | Fix |
|---|---|---|
| every Application `Unknown`, `failed to list refs … x509` | WARP (Cloudflare Gateway) intercepts TLS inside the nodes | `warp-cli disconnect`, then `kubectl -n argocd annotate application root-app argocd.argoproj.io/refresh=hard --overwrite` |
| `make prereqs` ✗ port 8088 | another kind cluster or process owns the ingress port | stop it (`kind delete cluster --name <other>`) |
| `make wait` never ends on `root-app(Synced/Degraded)` | a use case's workloads are Degraded before their first pipeline | expected before `make build pipeline`; `wait` ignores root-app in the platform scope |
| `pip install` fails inside `docker build` (`name resolution`) | the builder has no DNS on this machine | `DOCKER_BUILD_HOST_NETWORK=1` (default) — `make prereqs` probes it |
| predictor `Init:CrashLoopBackOff`, `No model found` | version `"0"` or an empty bucket: nothing published yet | `make pipeline` (first run bootstraps v1) |
| `evaluate` fails with `AccessDenied` after moving a use case to other buckets | the registry's `serving_uri` / `reference_uri` point at the old bucket | migrate the objects and re-tag, or reset the use case's registered models |
| API 503 right after disabling Argo Rollouts | the Service still selects `rollouts-pod-template-hash` | `make module DISABLE=argo-rollouts` runs the hook; by hand: patch the selector out |
| a retry of an aborted canary fails again immediately | the 2-minute rate window still contains the outage | wait two minutes, retry |
| `make build/pipeline/smoke`: "use case not deployed by the demo" | its group is opt-in (commented) in `apps/` and `projects/` | `make use-case ENABLE=<uc> COMMIT=1` |
| `promote` fails with `could not push` | the token in `pipeline-git-credentials` cannot write | `gh auth login` with a token that can push, `make secrets` |
