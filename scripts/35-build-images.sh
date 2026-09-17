#!/usr/bin/env bash
# Builds the use-case images and loads them into the kind nodes. No registry
# in the demo: `kind load` + imagePullPolicy IfNotPresent. Rebuilding with the
# same tag and reloading replaces the image; `kubectl rollout restart` picks it.
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require docker kind git

GIT_COMMIT="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
VERSION="${VERSION:-0.1.0}"
NETWORK_ARG=()
# On this laptop Docker's builder resolves no DNS unless it uses the host network.
[[ "${DOCKER_BUILD_HOST_NETWORK:-1}" == "1" ]] && NETWORK_ARG=(--network host)

step "ctsteps-base:${VERSION}"
docker build "${NETWORK_ARG[@]}" -q -t "ctsteps-base:${VERSION}" "${REPO_ROOT}/libs/ctsteps" >/dev/null
info "built"

step "listing-engine-steps:${VERSION}"
docker build "${NETWORK_ARG[@]}" -q --build-arg "BASE=ctsteps-base:${VERSION}" \
  -t "listing-engine-steps:${VERSION}" "${REPO_ROOT}/use-cases/listing-engine/plugin" >/dev/null
info "built"

step "listing-engine-api:${VERSION}"
docker build "${NETWORK_ARG[@]}" -q --build-arg "GIT_COMMIT=${GIT_COMMIT}" \
  -t "listing-engine-api:${VERSION}" "${REPO_ROOT}/use-cases/listing-engine/api" >/dev/null
info "built (git ${GIT_COMMIT})"

step "Loading into kind '${CLUSTER}'"
for img in "listing-engine-steps:${VERSION}" "listing-engine-api:${VERSION}"; do
  kind load docker-image --name "${CLUSTER}" "$img" >/dev/null 2>&1 && info "✓ $img"
done
