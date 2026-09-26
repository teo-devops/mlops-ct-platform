# Profiles: demo (kind) · prod (bare-metal) · aws

Same modules, same contracts, same charts. What changes is the values — and who operates each piece.

| Contract / concern | demo — `gitops/environments/demo` (runs) | prod — bare-metal (values illustrative) | aws (values illustrative) |
|---|---|---|---|
| Kubernetes | kind 1 cp + 2 workers, kindnet | kubeadm + Cilium eBPF | EKS + Karpenter |
| GitOps engine | Argo CD single instance, admin only | Argo CD HA, SSO via Dex, RBAC per AppProject | same |
| Ingress | ingress-nginx, `*.localhost:8088` | MetalLB + ingress-nginx/Gateway API, TLS via cert-manager | ALB / API Gateway |
| Artifact store | SeaweedFS single node, local-path PVC | SeaweedFS cluster on Longhorn (or S3) | S3 + IRSA |
| Model registry | MLflow, sqlite on PVC | MLflow + managed Postgres, artifacts on SeaweedFS/S3 | MLflow + RDS + S3 |
| Serving | KServe Standard, no autoscaling | KServe + Istio/Gateway, HPA on QPS, canary via Rollouts/KServe | same on EKS |
| Orchestration | Argo Workflows (Airflow as an opt-in module, exercised) | Airflow (ETL, sensors) + Argo Workflows/KFP + Katib | MWAA + KFP on EKS (or SageMaker Pipelines) |
| Events | prediction log on S3 (Redpanda as an opt-in module, exercised) | Kafka via Strimzi (example in docs/modules/event-bus.md) | MSK |
| Monitoring | kube-prometheus-stack mini, Pushgateway | full stack + Alertmanager routes | Amazon Managed Prometheus + Grafana |
| Model monitoring | Evidently on a CronWorkflow | Evidently consuming Kafka, labels feedback loop | same |
| Secrets | random, cluster-only, created by script | External Secrets / Vault | IRSA + Secrets Manager |
| Backups | none | Velero → SeaweedFS | Velero → S3 |

`gitops/environments/prod/` and `gitops/environments/aws/` hold only READMEs and `values-prod.yaml` / `values-aws.yaml`
files next to the charts that have profile-specific values. They are not reconciled by anything:
they document the shape, they are not a second architecture.
