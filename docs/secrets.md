# Secrets and other out-of-band state

Nothing sensitive is in Git — no SOPS, no Sealed Secrets, on purpose (docs/decisions.md). Two layers:

| Layer | What | Created by | Rotation |
|---|---|---|---|
| Argo CD operation | `argocd/repo-mlops-ct-platform` (read token of this private repo), `argocd-initial-admin-secret` | `scripts/20-install.sh` phase 0 / Argo CD | `scripts/credentials.sh add` |
| Workload secrets | `minio/minio-root`, `minio/minio-users`, `mlflow/mlflow-s3-credentials`, `listing-engine-serving/models-s3-credentials`, `listing-engine-pipelines/pipeline-s3-credentials`, `listing-engine-pipelines/pipeline-git-credentials`, `listing-engine-api/api-s3-credentials`, `observability/grafana-admin` | `scripts/15-demo-secrets.sh` — random values, **before the first sync** (Jobs and InferenceServices need them on their first attempt) | delete the Secret, rerun the script, `kubectl rollout restart` |

The same script creates `listing-engine-pipelines/ct-data-source`: a ConfigMap that stands in for
the upstream data platform ("which world does ingest see"). It is state of the outside world, not
configuration of the platform, so it is not in Git either; `make drift` flips it.

`make status` prints every password. In production the workload secrets come from a secret manager
(External Secrets, Vault) and the Git credential is a bot token scoped to one repository; in the
aws profile S3 credentials disappear in favour of IRSA.
