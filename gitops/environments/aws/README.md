# aws profile — illustrative

Same modules on managed services: EKS + Karpenter, S3 instead of SeaweedFS (the `seaweedfs` workload is
disabled — one line in `platform/kustomization.yaml` and one in `apps/kustomization.yaml`), IRSA
annotations on the predictor and pipeline ServiceAccounts instead of S3 Secrets, MWAA as the ETL
orchestrator adapter, MSK for the event-bus module, Amazon Managed Prometheus/Grafana for the
monitoring contract. The step contract and the use case do not change. See docs/design/profiles.md.
