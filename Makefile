# mlops-ct-platform — demo profile on kind.
#
#   make demo        everything: up secrets bootstrap wait build pipeline smoke
#   make up          kind cluster + ingress-nginx + image preload
#   make secrets     namespaces + demo Secrets (never in Git)
#   make bootstrap   Argo CD from the chart + root-app (scripts/platform/04-install.sh)
#   make wait        wait until the platform modules are Synced/Healthy
#   make build       build the use-case images and load them into kind   (USE_CASE=listing-engine)
#   make pipeline    run the continuous-training pipeline for every model
#   make promote     promote (or roll back to) a version: make promote MODEL=fraud VERSION=2
#   make smoke       end-to-end request + fallback drill + network-policy test
#   make drift       send drifted traffic and watch the loop retrain
#   make status      Applications, pods, URLs and demo passwords
#   make down        delete the cluster
#   make validate    static checks (coherence, render, helm lint, ruff, pytest)
#   make venv        dev virtualenv with every python package (needed by validate)
#   make deploy-local  same charts and values with helm directly, no Argo CD
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
export CLUSTER ?= ct
# The use case whose flow `make build/pipeline/promote/smoke/drift` runs. The
# platform itself knows nothing about it: those targets delegate to
# use-cases/$(USE_CASE)/scripts/. Any directory with those scripts works.
USE_CASE ?= listing-engine
UC := use-cases/$(USE_CASE)/scripts
# python with the dev dependencies (make venv creates it)
PY := $(if $(wildcard .venv-dev/bin/python),$(CURDIR)/.venv-dev/bin/python,python3)

.PHONY: help prereqs up secrets bootstrap wait build pipeline promote smoke drift status down demo validate deploy-local render lint test venv

help:
	@sed -n 's/^#   \(make [a-z-]*\) *\(.*\)/  \1\t\2/p' Makefile

prereqs:    ; @scripts/cluster/01-prereqs.sh
up:         ; @scripts/cluster/02-up.sh
secrets:    ; @scripts/platform/03-secrets.sh
bootstrap:  ; @ASSUME_YES=1 scripts/platform/04-install.sh
wait:       ; @scripts/platform/05-wait.sh
build:      ; @$(UC)/06-build-images.sh
pipeline:   ; @$(UC)/07-run-pipeline.sh
promote:    ; @$(UC)/promote.sh $(MODEL) $(VERSION) $(or $(TRIGGER),manual)
smoke:      ; @$(UC)/08-smoke.sh
drift:      ; @$(UC)/09-induce-drift.sh
status:     ; @scripts/platform/status.sh
down:       ; @scripts/cluster/10-down.sh
deploy-local: ; @scripts/platform/deploy-local.sh

demo: up secrets bootstrap wait build pipeline smoke

render:
	@scripts/repo/render.sh rendered

lint:
	@python3 scripts/repo/validate-coherence.py
	@kubectl kustomize gitops/environments/demo > /dev/null && kubectl kustomize gitops/bootstrap > /dev/null && echo "✓ kustomize renders"
	@for c in workloads/*/ use-cases/*/workloads/*/; do [ -f "$$c/Chart.yaml" ] && helm lint "$$c" -f "$$c/values.yaml" -f "$$c/values-demo.yaml" --quiet && echo "✓ helm lint $$c"; done; true
	@if $(PY) -m ruff --version >/dev/null 2>&1; then $(PY) -m ruff check libs use-cases && $(PY) -m ruff format --check libs use-cases && echo "✓ ruff"; else echo "ruff not installed (make venv): skipping python lint"; fi

test:
	@for d in libs/ctsteps use-cases/*/plugin use-cases/*/api; do [ -f "$$d/pyproject.toml" ] || continue; \
	  echo "== $$d"; (cd "$$d" && MLFLOW_DISABLE_AGENT_HINT=1 $(PY) -m pytest -q 2>&1 | tail -1) || exit 1; done

venv:
	python3 -m venv .venv-dev && .venv-dev/bin/pip install -q --upgrade pip \
	  && .venv-dev/bin/pip install -q -e "libs/ctsteps[dev]" -e "use-cases/listing-engine/plugin[dev]" -e "use-cases/listing-engine/api[dev]"

validate: lint test
