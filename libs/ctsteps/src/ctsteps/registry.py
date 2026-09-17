"""Model-registry contract: MLflow tracking + registered models with aliases.

Names are `<use_case>-<model>`; aliases `champion` (serving) and `challenger`
(last candidate that passed the gate but is not yet promoted, or was demoted).
"""

from __future__ import annotations

import mlflow
from mlflow import MlflowClient

CHAMPION = "champion"
CHALLENGER = "challenger"


def registered_name(use_case: str, model: str) -> str:
    return f"{use_case}-{model}"


def experiment_name(use_case: str, model: str) -> str:
    return f"{use_case}/{model}"


def setup(tracking_uri: str, use_case: str, model: str) -> str:
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.set_experiment(experiment_name(use_case, model)).experiment_id


def champion_version(client: MlflowClient, name: str):
    """The model version behind the `champion` alias, or None."""
    try:
        return client.get_model_version_by_alias(name, CHAMPION)
    except mlflow.exceptions.MlflowException:
        return None
