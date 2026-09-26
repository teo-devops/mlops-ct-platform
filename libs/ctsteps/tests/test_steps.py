from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pandas as pd
import pytest

from ctsteps import cli
from ctsteps.contracts import ColumnCheck, ModelSpec
from ctsteps.steps import evaluate, promote, validate


def read_result(tmp_path):
    return json.loads((tmp_path / "outputs" / "result.json").read_text())


def test_validate_reports_violations():
    df = pd.DataFrame({"a": [1, 2, None], "b": ["x", "y", "z"]})
    schema = {
        "a": ColumnCheck(dtype="number", min=2, max_null_ratio=0.1),
        "b": ColumnCheck(dtype="string", allowed=("x", "y")),
        "c": ColumnCheck(dtype="string"),
    }
    v = validate.check_frame(df, schema)
    assert any("null ratio" in x for x in v)
    assert any("min 1" in x for x in v)
    assert any("unexpected values" in x for x in v)
    assert any("c: missing column" in x for x in v)
    assert (
        validate.check_frame(
            pd.DataFrame({"a": [2.0, 3.0]}), {"a": ColumnCheck(dtype="number", min=2)}
        )
        == []
    )


def test_gate_decision():
    spec = ModelSpec(
        name="m", target="t", features=("f",), primary_metric="f1", min_improvement=0.01
    )
    assert evaluate.decide(spec, 0.5, None) == (True, "no champion yet")
    assert evaluate.decide(spec, 0.52, 0.5)[0] is True
    assert evaluate.decide(spec, 0.505, 0.5)[0] is False
    lower = ModelSpec(
        name="m", target="t", features=("f",), primary_metric="rmse", higher_is_better=False
    )
    assert lower and evaluate.decide(lower, 0.4, 0.5)[0] is True


def test_bump_version_keeps_comments():
    text = """models:
  categorizer:
    # managed by ctsteps promote
    version: "3"
    minReplicas: 1
  fraud:
    version: "7"
"""
    out = promote.bump_version(text, "fraud", 8)
    assert 'version: "8"' in out and 'version: "3"' in out and "# managed" in out
    out = promote.bump_version(text, "categorizer", 4)
    assert out.count('version: "4"') == 1 and 'version: "7"' in out
    with pytest.raises(SystemExit):
        promote.bump_version(text, "missing", 1)


def test_push_bump_commits_once_and_is_idempotent(tmp_path):
    """A bump is one commit on the branch; bumping to the version Git already has is a no-op."""

    def sh(*args, cwd):
        return subprocess.run(
            args, cwd=cwd, check=True, text=True, capture_output=True
        ).stdout.strip()

    origin, work = tmp_path / "origin.git", tmp_path / "work"
    sh("git", "init", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    sh("git", "clone", str(origin), str(work), cwd=tmp_path)
    (work / "values.yaml").write_text('models:\n  fraud:\n    version: "1"\n')
    sh("git", "add", "values.yaml", cwd=work)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init", cwd=work)
    sh("git", "push", "origin", "HEAD:main", cwd=work)
    ctx = SimpleNamespace(
        settings=SimpleNamespace(
            git_repo=str(origin),
            git_branch="main",
            git_user="",
            git_token="t",
            values_file="values.yaml",
        ),
        use_case=SimpleNamespace(name="uc"),
        spec=SimpleNamespace(name="fraud"),
        run_id="run-1",
        serving_uri=lambda v: f"s3://uc-models/uc/fraud/v{v}",
    )
    head = sh("git", "rev-parse", "main", cwd=origin)
    assert promote.push_bump(ctx, 1, "manual") == head  # already v1: no commit
    assert sh("git", "rev-parse", "main", cwd=origin) == head
    new = promote.push_bump(ctx, 2, "manual")
    assert new != head and sh("git", "rev-parse", "main", cwd=origin) == new
    assert 'version: "2"' in sh("git", "show", "main:values.yaml", cwd=origin)


def test_pipeline_end_to_end(env):
    """ingest -> validate -> preprocess -> train -> evaluate -> register -> promote(dry) -> second run loses the gate."""
    run = ["--model", "colour", "--run-id", "run1"]
    cli.main(["ingest", *run, "--rows", "400"])
    assert read_result(env)["rows"] == 400
    cli.main(["validate", *run])
    assert read_result(env)["ok"] is True
    cli.main(["preprocess", *run, "--reference-rows", "100"])
    assert read_result(env)["train_rows"] == 300
    cli.main(["train", *run, "--trigger", "test"])
    mlflow_run = read_result(env)["mlflow_run_id"]
    cli.main(["evaluate", *run, "--mlflow-run-id", mlflow_run])
    r = read_result(env)
    assert r["promote"] is True and r["reason"] == "no champion yet" and r["candidate"] > 0.9
    cli.main(["register", *run, "--mlflow-run-id", mlflow_run])
    r = read_result(env)
    assert r["version"] == 1 and r["serving_uri"] == "s3://models/toy/colour/v1"
    cli.main(["promote", *run, "--version", "1", "--dry-run"])
    assert read_result(env)["commit"] == "dry-run"

    # The serving artefact must load without the use-case package: plain sklearn.
    import io

    import boto3
    import joblib

    body = (
        boto3.client("s3")
        .get_object(Bucket="models", Key="toy/colour/v1/model.joblib")["Body"]
        .read()
    )
    est = joblib.load(io.BytesIO(body))
    assert list(est.predict(pd.DataFrame({"text": ["sky sea"], "size": [20.0]}))) == ["blue"]

    # Second run with the same data: no improvement -> gate refuses.
    run2 = ["--model", "colour", "--run-id", "run2"]
    for step in (
        ["ingest", "--rows", "400"],
        ["validate"],
        ["preprocess", "--reference-rows", "100"],
        ["train"],
    ):
        cli.main([step[0], *run2, *step[1:]])
    mlflow_run2 = read_result(env)["mlflow_run_id"]
    cli.main(["evaluate", *run2, "--mlflow-run-id", mlflow_run2])
    r = read_result(env)
    assert r["promote"] is False and r["champion_version"] == 1


def test_validate_gate_blocks_bad_data(env, monkeypatch):
    run = ["--model", "colour", "--run-id", "bad"]
    cli.main(["ingest", *run, "--rows", "50"])
    # Corrupt the raw dataset: negative sizes violate the schema.
    import boto3

    from ctsteps import io_s3

    s3 = boto3.client("s3")
    df = io_s3.get_parquet(s3, "s3://datasets/toy/colour/bad/raw.parquet")
    df["size"] = -1.0
    io_s3.put_parquet(s3, "s3://datasets/toy/colour/bad/raw.parquet", df)
    with pytest.raises(SystemExit):
        cli.main(["validate", *run])
    assert read_result(env)["ok"] is False


def test_regression_model_splits_without_stratifying_and_gates_on_mae(env):
    """A continuous target: preprocess must not stratify; the gate reads higher_is_better=False."""
    run = ["--model", "weight", "--run-id", "reg1"]
    cli.main(["ingest", *run, "--rows", "300"])
    cli.main(["validate", *run])
    cli.main(["preprocess", *run, "--reference-rows", "50"])
    cli.main(["train", *run, "--trigger", "test"])
    mlflow_run = json.loads((env / "outputs" / "result.json").read_text())["mlflow_run_id"]
    cli.main(["evaluate", *run, "--mlflow-run-id", mlflow_run])
    res = json.loads((env / "outputs" / "result.json").read_text())
    assert res["promote"] is True and res["primary_metric"] == "mae"


def test_sample_prints_feature_records(env, capsys):
    cli.main(["sample", "--model", "colour", "--rows", "5", "--profile", "drift"])
    records = json.loads(capsys.readouterr().out)
    assert len(records) == 5 and set(records[0]) == {"text", "size"}
