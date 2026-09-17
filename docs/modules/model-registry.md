# Module: model-registry

| | |
|---|---|
| **Contract** | MLflow tracking + registry; aliases `champion` / `challenger` / `previous` |
| **Demo implementation** | community-charts/mlflow, sqlite backend on a PVC, artifacts on the `mlflow` bucket |
| **Pinned version** | chart 1.11.7 (MLflow 3.16.0) |
| **Namespace** | mlflow |
| **Replace with** | MLflow with managed Postgres (prod); any registry with aliases and version tags could back the same step code via `ctsteps/registry.py` |
| **Disable** | remove the line and reimplement `registry.py` |

Wave 2. Host-header validation in MLflow 3 means both the ingress host (with port) and the in-cluster Service names are allow-listed. Two uvicorn workers and a 2 GiB limit (four workers were OOM-killed at 1 GiB). The metrics dir is an emptyDir because the root filesystem is read-only.
