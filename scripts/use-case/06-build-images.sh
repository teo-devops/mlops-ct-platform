#!/usr/bin/env bash
# Builds the use case's images and loads them into the kind nodes. No registry
# in the demo: `kind load` + imagePullPolicy IfNotPresent. Rebuilding with the
# same tag and reloading replaces the image; a rollout restart picks it.
. "$(dirname "${BASH_SOURCE[0]}")/lib-uc.sh"
require docker kind git

GIT_COMMIT="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
VERSION="${VERSION:-0.1.0}"
NETWORK_ARG=()
# On this laptop Docker's builder resolves no DNS unless it uses the host network.
[[ "${DOCKER_BUILD_HOST_NETWORK:-1}" == "1" ]] && NETWORK_ARG=(--network host)
IMAGES=()

step "ctsteps-base:${VERSION}"
docker build "${NETWORK_ARG[@]}" -q -t "ctsteps-base:${VERSION}" "${REPO_ROOT}/libs/ctsteps" >/dev/null
info "built"

step "${UC_NAME}-steps:${VERSION}"
docker build "${NETWORK_ARG[@]}" -q --build-arg "BASE=ctsteps-base:${VERSION}" \
  -t "${UC_NAME}-steps:${VERSION}" "${UC_DIR}/plugin" >/dev/null
info "built"; IMAGES+=("${UC_NAME}-steps:${VERSION}")

if [[ "$UC_API_ENABLED" == "true" ]]; then
  step "ctserve-base:${VERSION}"
  docker build "${NETWORK_ARG[@]}" -q -t "ctserve-base:${VERSION}" "${REPO_ROOT}/libs/ctserve" >/dev/null
  info "built"
  step "${UC_NAME}-api:${VERSION}"
  docker build "${NETWORK_ARG[@]}" -q --build-arg "BASE=ctserve-base:${VERSION}" --build-arg "GIT_COMMIT=${GIT_COMMIT}" \
    -t "${UC_NAME}-api:${VERSION}" "${UC_DIR}/api" >/dev/null
  info "built (git ${GIT_COMMIT})"; IMAGES+=("${UC_NAME}-api:${VERSION}")
fi

step "Loading into kind '${CLUSTER}'"
for img in "${IMAGES[@]}"; do
  kind load docker-image --name "${CLUSTER}" "$img" >/dev/null 2>&1 && info "✓ $img"
done
