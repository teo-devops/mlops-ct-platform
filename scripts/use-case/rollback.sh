#!/usr/bin/env bash
# Roll a model back to its previous champion — no version number to look up:
# the registry keeps the alias `previous` (set by every promotion).
#   USE_CASE=<uc> scripts/use-case/rollback.sh <model>
. "$(dirname "${BASH_SOURCE[0]}")/lib-uc.sh"
require curl python3
MODEL="${1:?model}"
MLFLOW="${MLFLOW_URL:-http://mlflow.localhost:8088}"
name="${UC_NAME}-${MODEL}"
prev="$(curl -sf "${MLFLOW}/api/2.0/mlflow/registered-models/alias?name=${name}&alias=previous" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["model_version"]["version"])' 2>/dev/null || true)"
[[ -n "$prev" ]] || die "no previous champion of ${name} in the registry (${MLFLOW}, alias previous): nothing to roll back to"
cur="$(curl -sf "${MLFLOW}/api/2.0/mlflow/registered-models/alias?name=${name}&alias=champion" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["model_version"]["version"])' 2>/dev/null || echo '?')"
step "Rolling back ${UC_NAME}/${MODEL}: champion v${cur} -> previous v${prev}"
exec "$(dirname "${BASH_SOURCE[0]}")/promote.sh" "$MODEL" "$prev" rollback
