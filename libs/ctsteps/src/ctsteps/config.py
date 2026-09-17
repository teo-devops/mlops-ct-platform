"""Runtime configuration of a step, all from the environment.

These names ARE the contract between the platform and the steps: the
orchestrator adapter sets them from the Secrets/ConfigMaps of the pipelines
namespace, whatever the orchestrator.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise SystemExit(f"missing environment variable {name}")
    return value


@dataclass(frozen=True)
class Settings:
    # artifact store (S3 API)
    s3_endpoint: str  # e.g. http://minio.minio.svc.cluster.local:9000
    datasets_bucket: str
    models_bucket: str
    predictions_bucket: str
    # model registry (MLflow API)
    mlflow_tracking_uri: str
    # promotion target (GitOps)
    git_repo: str
    git_branch: str
    git_user: str
    git_token: str
    values_file: str
    # where the orchestrator reads the step result
    outputs_dir: Path

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            # empty = AWS default resolution (real S3, or moto in tests)
            s3_endpoint=os.environ.get("S3_ENDPOINT_URL", ""),
            datasets_bucket=_env("CT_DATASETS_BUCKET", "datasets"),
            models_bucket=_env("CT_MODELS_BUCKET", "models"),
            predictions_bucket=_env("CT_PREDICTIONS_BUCKET", "predictions"),
            mlflow_tracking_uri=_env(
                "MLFLOW_TRACKING_URI", "http://mlflow.mlflow.svc.cluster.local"
            ),
            git_repo=os.environ.get("GIT_REPO", ""),
            git_branch=os.environ.get("GIT_BRANCH", "main"),
            git_user=os.environ.get("GIT_USER", ""),
            git_token=os.environ.get("GIT_TOKEN", ""),
            values_file=os.environ.get("CT_PROMOTE_VALUES_FILE", ""),
            outputs_dir=Path(os.environ.get("CT_OUTPUTS_DIR", "/tmp/outputs")),
        )
