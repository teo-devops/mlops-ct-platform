# mlops-ct-platform — demo profile on kind.  `make` (or `make help`) lists the commands.
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
export CLUSTER ?= ct
# The use case the use-case commands act on: USE_CASE=<name>, default = the first
# use case the demo deploys (gitops/environments/demo/apps/kustomization.yaml).
# One demo per use case: `make demo USE_CASE=<name>`. The flow scripts are the
# platform's (scripts/use-case/); they read use-cases/$(USE_CASE)/usecase.yaml.
USE_CASE ?= $(shell sed -nE 's/^\s*-\s*([a-z0-9-]+)\s*$$/\1/p' gitops/environments/demo/apps/kustomization.yaml | grep -vx shared | head -1)
export USE_CASE
UC := scripts/use-case
# python with the dev dependencies (make venv creates it)
PY := $(if $(wildcard .venv-dev/bin/python),$(CURDIR)/.venv-dev/bin/python,python3)

.PHONY: help prereqs demo drift status down pipeline promote rollback smoke build \
        module use-case new-use-case up secrets bootstrap wait check-use-case \
        validate lint test venv render

help:
	@awk 'BEGIN {FS=":.*##"} \
	  /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next} \
	  /^[a-z-]+:.*##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n  One demo per use case: USE_CASE=<name> (deployed ones: make use-case; now defaulting to '%s').\n  Every UI answers on http://<name>.localhost:8088\n\n" "$(USE_CASE)"

##@ Start here
prereqs: ## check tools, credentials, network and memory — and what the demo will deploy
	@scripts/cluster/01-prereqs.sh
demo: check-use-case up secrets bootstrap wait build pipeline smoke status ## everything: cluster → platform → use case → smoke (≈15 min)
	@printf "\n\033[1mDemo up.\033[0m Next: \033[36mmake drift\033[0m closes the loop (drift → retrain → promote → new version served).\n\n"
drift: check-use-case ## close the loop: the world drifts → retrain → promote (commit) → new version served
	@$(UC)/09-induce-drift.sh
status: ## what is running: Applications, served models, pipelines, UIs and passwords
	@scripts/platform/status.sh
down: ## delete the cluster
	@scripts/cluster/10-down.sh

##@ Operate a use case  (USE_CASE=<name>)
pipeline: check-use-case ## train every model now (the first run bootstraps v1)
	@$(UC)/07-run-pipeline.sh
promote: check-use-case ## promote a registry version: MODEL=<m> VERSION=<n>
	@$(UC)/promote.sh $(MODEL) $(VERSION) $(or $(TRIGGER),manual)
rollback: check-use-case ## back to the previous champion: MODEL=<m>
	@$(UC)/rollback.sh $(MODEL)
smoke: check-use-case ## real request, fallback drill, network-policy probe
	@$(UC)/08-smoke.sh
build: check-use-case ## rebuild the use case's images into kind
	@$(UC)/06-build-images.sh

##@ Shape the demo
module: ## opt-in platform modules: ENABLE=<m> | DISABLE=<m> | (status)   [COMMIT=1]
	@if [ -n "$(ENABLE)" ]; then scripts/platform/module.sh enable "$(ENABLE)"; elif [ -n "$(DISABLE)" ]; then scripts/platform/module.sh disable "$(DISABLE)"; else scripts/platform/module.sh status; fi
use-case: ## use cases the demo deploys: ENABLE=<uc> | DISABLE=<uc> | (status)   [COMMIT=1]
	@if [ -n "$(ENABLE)" ]; then scripts/use-case/toggle.sh enable "$(ENABLE)"; elif [ -n "$(DISABLE)" ]; then scripts/use-case/toggle.sh disable "$(DISABLE)"; else scripts/use-case/toggle.sh status; fi
new-use-case: ## scaffold + register a use case: NAME=<uc> MODELS=a,b [TASK=regression] [API=false]
	@$(PY) scripts/repo/new-use-case.py "$(NAME)" --models "$(MODELS)" --task "$(or $(TASK),classification)" $(if $(filter false,$(API)),--no-api,)

##@ Step by step  (what `make demo` runs, in order)
up: ## 02  kind cluster + ingress-nginx + images of the enabled modules
	@scripts/cluster/02-up.sh
secrets: ## 03  namespaces and Secrets of the platform and the deployed use cases (never in Git)
	@scripts/platform/03-secrets.sh
bootstrap: ## 04  Argo CD from the chart + root-app; from here on everything is a commit
	@ASSUME_YES=1 scripts/platform/04-install.sh
wait: ## 05  wait until the platform modules are Synced/Healthy
	@scripts/platform/05-wait.sh
# then 06 build · 07 pipeline · 08 smoke (above)

##@ Repository
validate: lint test ## static checks + tests (coherence, kustomize, helm lint, ruff, pytest)
venv: ## dev virtualenv with every python package (needed by validate)
	python3 -m venv .venv-dev && .venv-dev/bin/pip install -q --upgrade pip \
	  && .venv-dev/bin/pip install -q -e "libs/ctsteps[dev]" -e "libs/ctserve[dev]" \
	  $$(for d in use-cases/*/plugin use-cases/*/api; do [ -f "$$d/pyproject.toml" ] && printf -- '-e %s[dev] ' "$$d"; done)
render: ## what Argo CD would apply (rendered manifests under rendered/)
	@scripts/repo/render.sh rendered

# --- internals -------------------------------------------------------------
# The use-case commands refuse a use case the demo does not deploy.
check-use-case:
	@grep -Eq "^\s*-\s*$(USE_CASE)\s*$$" gitops/environments/demo/apps/kustomization.yaml \
	  || { printf "\n  use case '%s' is not deployed by the demo.\n  Deploy it:  make use-case ENABLE=%s COMMIT=1   (then rerun)\n\n" "$(USE_CASE)" "$(USE_CASE)"; exit 1; }
lint:
	@python3 scripts/repo/validate-coherence.py
	@kubectl kustomize gitops/environments/demo > /dev/null && kubectl kustomize gitops/bootstrap > /dev/null && echo "✓ kustomize renders"
	@for c in workloads/*/ use-cases/*/workloads/*/; do [ -f "$$c/Chart.yaml" ] && helm lint "$$c" -f "$$c/values.yaml" -f "$$c/values-demo.yaml" --quiet && echo "✓ helm lint $$c"; done; true
	@if $(PY) -m ruff --version >/dev/null 2>&1; then $(PY) -m ruff check libs use-cases orchestrators && $(PY) -m ruff format --check libs use-cases orchestrators && echo "✓ ruff"; else echo "ruff not installed (make venv): skipping python lint"; fi
test:
	@for d in libs/* use-cases/*/plugin use-cases/*/api; do [ -f "$$d/pyproject.toml" ] || continue; \
	  echo "== $$d"; (cd "$$d" && MLFLOW_DISABLE_AGENT_HINT=1 $(PY) -m pytest -q 2>&1 | tail -1) || exit 1; done
