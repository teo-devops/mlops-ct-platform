# Module: artifact-store

| | |
|---|---|
| **Contract** | S3 API; buckets `datasets`, `models`, `predictions`, `mlflow`; least-privilege users |
| **Demo implementation** | MinIO single node (`workloads/minio`), a workload rather than a platform module because it is a shared service consumed over the network |
| **Pinned version** | quay.io/minio/minio RELEASE.2025-09-07T16-13-09Z (sha256:14cea493…) |
| **Namespace** | minio |
| **Replace with** | S3 (aws), replicated MinIO on Longhorn (prod, see teo-devops/minIO-docker) |
| **Disable** | remove `minio` from `apps/kustomization.yaml` and point every `S3_ENDPOINT_URL` elsewhere |

A PostSync Job (`mc`) provisions buckets, users and policies idempotently on every sync; the user list in `values.yaml` is the access matrix of the platform. Docker Hub no longer serves MinIO images; the tag is pinned on quay.io and preloaded into kind.
