#!/usr/bin/env bash
# Waits until every Application except the use-case ones is Synced/Healthy.
# The use-case serving Application stays Progressing until the first pipeline
# run publishes a model: that is expected, not a failure.
. "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"
require kubectl
require_kind_context
TIMEOUT="${TIMEOUT:-1200}"

step "Waiting for the platform (timeout ${TIMEOUT}s)"
wait_apps_healthy "$TIMEOUT" '(?!listing-engine-).*' || die "platform not healthy; inspect with: make status"
info "platform Synced/Healthy"
kubectl -n argocd get applications
