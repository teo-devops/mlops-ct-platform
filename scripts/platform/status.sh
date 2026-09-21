#!/usr/bin/env bash
# One screen with everything: Applications (with their owner group), every
# served model and pipeline in the cluster, unhealthy pods, URLs, passwords.
# Knows no use case by name.
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
require kubectl
require_kind_context

step "Argo CD Applications"
kubectl -n argocd get applications -o custom-columns='NAME:.metadata.name,GROUP:.metadata.labels.mlops-ct-platform\.dev/group,SYNC:.status.sync.status,HEALTH:.status.health.status,WAVE:.metadata.annotations.argocd\.argoproj\.io/sync-wave' 2>/dev/null

step "Served models (every namespace)"
kubectl get inferenceservices -A -o custom-columns='NAMESPACE:.metadata.namespace,MODEL:.metadata.name,VERSION:.metadata.labels.mlops-ct-platform\.dev/model-version,READY:.status.conditions[?(@.type=="Ready")].status,URI:.spec.predictor.model.storageUri' 2>/dev/null || info "no InferenceServices yet"

step "Pipelines (last 10, every namespace)"
kubectl get workflows -A --sort-by=.metadata.creationTimestamp -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,MODEL:.metadata.labels.ct\.mlops/model,TRIGGER:.metadata.labels.ct\.mlops/trigger,PHASE:.status.phase,STARTED:.status.startedAt' 2>/dev/null | tail -11

step "Pods not Running/Completed"
kubectl get pods -A --no-headers 2>/dev/null | grep -vE "Running|Completed" || info "none"

step "URLs (http://<name>.localhost:8088)"
printf '    %-16s %s\n' "Argo CD" "http://argocd.localhost:8088  admin / $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null | base64 -d)"
printf '    %-16s %s\n' "Argo Workflows" "http://argo.localhost:8088"
kubectl get ns airflow >/dev/null 2>&1 && printf '    %-16s %s\n' "Airflow" "http://airflow.localhost:8088  (opt-in module)"
printf '    %-16s %s\n' "MLflow" "http://mlflow.localhost:8088"
printf '    %-16s %s\n' "Grafana" "http://grafana.localhost:8088  admin / $(kubectl -n observability get secret grafana-admin -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d)"
printf '    %-16s %s\n' "Prometheus" "http://prometheus.localhost:8088"
printf '    %-16s %s\n' "MinIO console" "http://minio.localhost:8088  root / $(kubectl -n minio get secret minio-root -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' 2>/dev/null | base64 -d)"
for ing in $(kubectl get ingress -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.spec.rules[0].host}{"\n"}{end}' 2>/dev/null | grep -vE "^(argocd|argo|airflow|mlflow|observability|minio)/"); do
  printf '    %-16s %s\n' "${ing%%/*}" "http://${ing#*/}:8088"
done
