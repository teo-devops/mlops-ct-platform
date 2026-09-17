# mlops-ct-platform — demo profile on kind.
#
#   make demo        everything: up secrets bootstrap wait build pipeline smoke
#   make up          kind cluster + ingress-nginx + image preload
#   make secrets     namespaces + demo Secrets (never in Git)
#   make bootstrap   Argo CD from the chart + root-app (scripts/20-install.sh)
#   make wait        wait until the platform modules are Synced/Healthy
#   make build       build the use-case images and load them into kind
#   make pipeline    run the continuous-training pipeline for every model
#   make smoke       end-to-end request + fallback drill + network-policy test
#   make drift       send drifted traffic and watch the loop retrain
#   make status      Applications, pods, URLs and demo passwords
#   make down        delete the cluster
#   make validate    static checks (coherence, render, helm lint, ruff, pytest)
#   make deploy-local  same charts and values with helm directly, no Argo CD
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
export CLUSTER ?= ct

.PHONY: help prereqs up secrets bootstrap wait build pipeline smoke drift status down demo validate deploy-local render lint test

help:
	@sed -n 's/^#   \(make [a-z-]*\) *\(.*\)/  \1\t\2/p' Makefile

prereqs:    ; @scripts/00-check-prereqs.sh
up:         ; @scripts/10-kind-up.sh
secrets:    ; @scripts/15-demo-secrets.sh
bootstrap:  ; @ASSUME_YES=1 scripts/20-install.sh
wait:       ; @scripts/30-wait-platform.sh
build:      ; @scripts/35-build-images.sh
pipeline:   ; @scripts/40-run-pipeline.sh
smoke:      ; @scripts/50-smoke.sh
drift:      ; @scripts/55-induce-drift.sh
status:     ; @scripts/60-status.sh
down:       ; @scripts/99-down.sh
deploy-local: ; @scripts/25-deploy-local.sh

demo: up secrets bootstrap wait build pipeline smoke

render:
	@scripts/render.sh rendered

lint:
	@python3 scripts/validate-coherence.py
	@kubectl kustomize overlays/demo > /dev/null && kubectl kustomize bootstrap > /dev/null && echo "✓ kustomize renders"
	@for c in workloads/*/ use-cases/*/workloads/*/; do [ -f "$$c/Chart.yaml" ] && helm lint "$$c" -f "$$c/values.yaml" -f "$$c/values-demo.yaml" --quiet && echo "✓ helm lint $$c"; done; true
	@if command -v ruff >/dev/null 2>&1; then ruff check libs use-cases && ruff format --check libs use-cases; else echo "ruff not installed: skipping python lint"; fi

test:
	@for d in libs/ctsteps use-cases/*/plugin use-cases/*/api; do [ -f "$$d/pyproject.toml" ] && (cd "$$d" && python3 -m pytest -q); done; true

validate: lint test
