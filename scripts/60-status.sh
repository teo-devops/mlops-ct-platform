#!/usr/bin/env bash
# One screen with everything: Applications, workloads, models, URLs, passwords.
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require kubectl
require_kind_context

step "Argo CD Applications"
kubectl -n argocd get applications -o custom-columns='NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,WAVE:.metadata.annotations.argocd\.argoproj\.io/sync-wave' 2>/dev/null

step "Models"
kubectl -n listing-engine-serving get inferenceservices -o custom-columns='MODEL:.metadata.name,VERSION:.metadata.labels.mlops-ct-platform\.dev/model-version,READY:.status.conditions[?(@.type=="Ready")].status,URI:.spec.predictor.model.storageUri' 2>/dev/null || info "serving not synced yet"

step "Pipelines (last 10)"
kubectl -n listing-engine-pipelines get workflows --sort-by=.metadata.creationTimestamp -o custom-columns='NAME:.metadata.name,MODEL:.metadata.labels.ct\.mlops/model,TRIGGER:.metadata.labels.ct\.mlops/trigger,PHASE:.status.phase,STARTED:.status.startedAt' 2>/dev/null | tail -11

step "Pods not Running/Completed"
kubectl get pods -A --no-headers 2>/dev/null | grep -vE "Running|Completed" || info "none"

step "URLs (http://<name>.localhost:8088)"
printf '    %-22s %s\n' "Argo CD" "http://argocd.localhost:8088  admin / $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null | base64 -d)"
printf '    %-22s %s\n' "Argo Workflows" "http://argo.localhost:8088"
printf '    %-22s %s\n' "MLflow" "http://mlflow.localhost:8088"
printf '    %-22s %s\n' "Grafana" "http://grafana.localhost:8088  admin / $(kubectl -n observability get secret grafana-admin -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d)"
printf '    %-22s %s\n' "Prometheus" "http://prometheus.localhost:8088"
printf '    %-22s %s\n' "MinIO console" "http://minio.localhost:8088  root / $(kubectl -n minio get secret minio-root -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' 2>/dev/null | base64 -d)"
printf '    %-22s %s\n' "Listing Engine API" "http://listing-engine.localhost:8088/docs"
