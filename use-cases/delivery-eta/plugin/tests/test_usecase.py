"""The plugin honours the contract, and the platform's pipeline runs on it end to end."""

from __future__ import annotations

import json

import pytest
from ctsteps import cli
from ctsteps.contracts import UseCase
from ctsteps.steps.drift import psi_by_column
from ctsteps.steps.validate import check_frame

from delivery_eta import data, use_case

MODELS = list(use_case.models)


def test_is_a_use_case_and_data_passes_its_own_schema():
    assert isinstance(use_case, UseCase)
    df = use_case.ingest(MODELS[0], profile=None, seed=1, rows=300)
    assert check_frame(df, use_case.schema(MODELS[0])) == []
    assert data.generate(seed=1, rows=50).equals(data.generate(seed=1, rows=50))


def test_drift_profile_is_visible_to_the_monitor():
    spec = use_case.models[MODELS[0]]
    ref = use_case.ingest(MODELS[0], profile=None, seed=1, rows=2000)
    quiet = use_case.ingest(MODELS[0], profile=None, seed=2, rows=2000)
    drifted = use_case.ingest(MODELS[0], profile="strike", seed=2, rows=2000)
    cols = list(spec.drift_columns)
    assert max(psi_by_column(ref, quiet, cols).values()) < 0.2
    assert max(psi_by_column(ref, drifted, cols).values()) > 0.3


@pytest.mark.parametrize("model", MODELS)
def test_pipeline_end_to_end(env, model):
    run = ["--model", model, "--run-id", "t1"]
    cli.main(["ingest", *run, "--rows", "400"])
    cli.main(["validate", *run])
    cli.main(["preprocess", *run, "--reference-rows", "100"])
    cli.main(["train", *run, "--trigger", "test"])
    mlflow_run = json.loads((env / "outputs" / "result.json").read_text())["mlflow_run_id"]
    cli.main(["evaluate", *run, "--mlflow-run-id", mlflow_run])
    res = json.loads((env / "outputs" / "result.json").read_text())
    assert res["promote"] is True and res["primary_metric"] == use_case.models[model].primary_metric
    cli.main(["register", *run, "--mlflow-run-id", mlflow_run])
    assert json.loads((env / "outputs" / "result.json").read_text())["version"] == 1
