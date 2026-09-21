# mlops-ct-platform — demo profile on kind.
#
#   make demo        everything: up secrets bootstrap wait build pipeline smoke
#   make up          kind cluster + ingress-nginx + image preload
#   make secrets     namespaces + demo Secrets (never in Git)
#   make bootstrap   Argo CD from the chart + root-app (scripts/platform/04-install.sh)
#   make wait        wait until the platform modules are Synced/Healthy
#   make build       build the use-case images and load them into kind   (USE_CASE=automated-listing-engine)
#   make pipeline    run the continuous-training pipeline for every model
#   make promote     promote (or roll back to) a version: make promote MODEL=fraud VERSION=2
#   make smoke       end-to-end request + fallback drill + network-policy test
#   make drift       send drifted traffic and watch the loop retrain
#   make status      Applications, pods, URLs and demo passwords
#   make down        delete the cluster
#   make validate    static checks (coherence, render, helm lint, ruff, pytest)
#   make new-use-case  scaffold + register a use case: make new-use-case NAME=x MODELS=a,b [TASK=regression] [API=false]
#   make module      opt-in platform modules: make module ENABLE=airflow | DISABLE=airflow | (status)   [COMMIT=1]
#   make use-case    use cases deployed by the demo: make use-case ENABLE=x | DISABLE=x | (status)  [COMMIT=1]
#   make venv        dev virtualenv with every python package (needed by validate)
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
export CLUSTER ?= ct
# The use case whose flow `make build/pipeline/promote/smoke/drift` runs. The
# flow scripts are the platform's (scripts/use-case/); they read
# use-cases/$(USE_CASE)/usecase.yaml and know nothing else about it.
USE_CASE ?= automated-listing-engine
export USE_CASE
UC := scripts/use-case
# python with the dev dependencies (make venv creates it)
PY := $(if $(wildcard .venv-dev/bin/python),$(CURDIR)/.venv-dev/bin/python,python3)

.PHONY: help prereqs up secrets bootstrap wait build pipeline promote smoke drift status down demo validate render new-use-case module use-case check-use-case lint test venv

help:
	@sed -n 's/^#   \(make [a-z-]*\) *\(.*\)/  \1\t\2/p' Makefile

prereqs:    ; @scripts/cluster/01-prereqs.sh
up:         ; @scripts/cluster/02-up.sh
secrets:    ; @scripts/platform/03-secrets.sh
bootstrap:  ; @ASSUME_YES=1 scripts/platform/04-install.sh
wait:       ; @scripts/platform/05-wait.sh
build:      check-use-case ; @$(UC)/06-build-images.sh
pipeline:   check-use-case ; @$(UC)/07-run-pipeline.sh
promote:    ; @$(UC)/promote.sh $(MODEL) $(VERSION) $(or $(TRIGGER),manual)
smoke:      ; @$(UC)/08-smoke.sh
drift:      ; @$(UC)/09-induce-drift.sh
status:     ; @scripts/platform/status.sh
down:       ; @scripts/cluster/10-down.sh

demo: check-use-case up secrets bootstrap wait build pipeline smoke

module:
	@if [ -n "$(ENABLE)" ]; then scripts/platform/module.sh enable "$(ENABLE)"; elif [ -n "$(DISABLE)" ]; then scripts/platform/module.sh disable "$(DISABLE)"; else scripts/platform/module.sh status; fi
use-case:
	@if [ -n "$(ENABLE)" ]; then scripts/use-case/toggle.sh enable "$(ENABLE)"; elif [ -n "$(DISABLE)" ]; then scripts/use-case/toggle.sh disable "$(DISABLE)"; else scripts/use-case/toggle.sh status; fi
# `make demo` and the use-case targets refuse a use case the demo does not deploy.
check-use-case:
	@grep -Eq "^\s*-\s*$(USE_CASE)\s*$$" gitops/environments/demo/apps/kustomization.yaml \
	  || { echo "use case '$(USE_CASE)' is not deployed by the demo: make use-case ENABLE=$(USE_CASE) COMMIT=1"; exit 1; }
new-use-case:
	@$(PY) scripts/repo/new-use-case.py "$(NAME)" --models "$(MODELS)" --task "$(or $(TASK),classification)" $(if $(filter false,$(API)),--no-api,)

render:
	@scripts/repo/render.sh rendered

lint:
	@python3 scripts/repo/validate-coherence.py
	@kubectl kustomize gitops/environments/demo > /dev/null && kubectl kustomize gitops/bootstrap > /dev/null && echo "✓ kustomize renders"
	@for c in workloads/*/ use-cases/*/workloads/*/; do [ -f "$$c/Chart.yaml" ] && helm lint "$$c" -f "$$c/values.yaml" -f "$$c/values-demo.yaml" --quiet && echo "✓ helm lint $$c"; done; true
	@if $(PY) -m ruff --version >/dev/null 2>&1; then $(PY) -m ruff check libs use-cases orchestrators && $(PY) -m ruff format --check libs use-cases orchestrators && echo "✓ ruff"; else echo "ruff not installed (make venv): skipping python lint"; fi

test:
	@for d in libs/* use-cases/*/plugin use-cases/*/api; do [ -f "$$d/pyproject.toml" ] || continue; \
	  echo "== $$d"; (cd "$$d" && MLFLOW_DISABLE_AGENT_HINT=1 $(PY) -m pytest -q 2>&1 | tail -1) || exit 1; done

venv:
	python3 -m venv .venv-dev && .venv-dev/bin/pip install -q --upgrade pip \
	  && .venv-dev/bin/pip install -q -e "libs/ctsteps[dev]" -e "libs/ctserve[dev]" \
	  $$(for d in use-cases/*/plugin use-cases/*/api; do [ -f "$$d/pyproject.toml" ] && printf -- '-e %s[dev] ' "$$d"; done)

validate: lint test
