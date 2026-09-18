#!/usr/bin/env bash
# Waits until every PLATFORM Application (modules + shared workloads) is
# Synced/Healthy. Use-case workloads are not waited for here: a serving
# workload stays Progressing until its first pipeline run publishes a model,
# which is expected. `SCOPE=<use-case>` waits for one use case instead.
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
require kubectl python3
require_kind_context
TIMEOUT="${TIMEOUT:-1200}"
SCOPE="${SCOPE:-platform}"

step "Waiting for ${SCOPE} Applications (timeout ${TIMEOUT}s)"
wait_apps_healthy "$TIMEOUT" "$SCOPE" || die "not healthy; inspect with: make status"
info "${SCOPE} Synced/Healthy"
kubectl -n argocd get applications
