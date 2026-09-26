# Module: artifact-store

| | |
|---|---|
| **Contract** | S3 API; buckets `datasets`, `models`, `predictions`, `mlflow`; least-privilege users |
| **Demo implementation** | SeaweedFS single node (`workloads/seaweedfs`), a workload rather than a platform module because it is a shared service consumed over the network |
| **Pinned version** | docker.io/chrislusf/seaweedfs 4.47 (sha256:ce9e796f…) |
| **Namespace** | seaweedfs |
| **Replace with** | S3 (aws), a SeaweedFS cluster on Longhorn (prod); any S3 store with per-bucket rights for named keys |
| **Disable** | remove `seaweedfs` from `apps/shared/kustomization.yaml` and point every `S3_ENDPOINT_URL` elsewhere |

The user list in `values.yaml` is the access matrix of the platform: it becomes SeaweedFS S3 identities with per-bucket actions (`rw` = Read+Write+List, `ro` = Read+List, `wo` = Write), rendered at start from the Secrets, so a changed list rolls the pod and a rotated key needs a restart. A PostSync Job (`weed shell`) creates the buckets idempotently on every sync. Console: `weed admin` at http://seaweedfs.localhost:8088 (root login); the filer UI is never exposed. MinIO was the implementation until its images left every public registry (docs/decisions.md #18).
