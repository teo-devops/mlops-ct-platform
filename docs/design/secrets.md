# Secrets and other out-of-band state

Nothing sensitive is in Git — no SOPS, no Sealed Secrets, on purpose ([decisions.md](../decisions.md)).
Everything out of band is created **before the first sync** of whatever needs it (Jobs and
InferenceServices need their credentials on the first attempt), by scripts that are idempotent
(existing Secrets are kept; rotation = delete + rerun + restart the consumer).

## Who creates what

| Layer | What | Created by |
|---|---|---|
| Argo CD operation | `argocd/repo-mlops-ct-platform` (read token of the repository — only needed by a private fork, the public repository is cloned anonymously), `argocd-initial-admin-secret` | `scripts/platform/04-install.sh` phase 0 / Argo CD; rotate with `scripts/platform/04-install.sh credential add` |
| Platform | `seaweedfs/seaweedfs-root`; `seaweedfs/seaweedfs-users` (one secret key per consumer user declared in `workloads/seaweedfs/values.yaml`); `mlflow/mlflow-s3-credentials`; `observability/grafana-admin`; when the opt-in airflow module is enabled: `airflow/airflow-postgres`, `airflow-metadata`, `airflow-fernet-key`, `airflow-api-secret-key`, `airflow-jwt-secret` | `scripts/platform/03-secrets.sh` |
| Use case | its namespaces; the credentials of **its own** artifact-store users `<uc>-reader/-pipeline/-api` (copied from `seaweedfs/seaweedfs-users` with `store_user_secret`); its Git credential for `promote`; its data-source state | `scripts/use-case/secrets.sh` for every `use-cases/*/usecase.yaml`, run last by `03-secrets.sh` |

The artifact-store **identities are platform property** (the access matrix is `users:` in the
SeaweedFS chart); a use case only receives the keys of the users it is allowed to use. Adding a use
case = adding its users to that matrix and delivering them in its own `secrets.sh`.

Human-facing passwords (Argo CD, Grafana, SeaweedFS root) are **known demo defaults** listed in the README so a fresh laptop needs no lookup; machine keys are random. `make status` prints the live values. In production the workload secrets come from a secret manager
(External Secrets, Vault) and the Git credential is a bot token scoped to one repository; in the
aws profile S3 credentials disappear in favour of IRSA.

Each use case lists the identities it uses in its `docs/architecture.md` ("Artifact-store identities used").
