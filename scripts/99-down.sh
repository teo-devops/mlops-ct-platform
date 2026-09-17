#!/usr/bin/env bash
# Deletes the kind cluster. Everything in it is reproducible from the repo.
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
kind delete cluster --name "${CLUSTER}"
