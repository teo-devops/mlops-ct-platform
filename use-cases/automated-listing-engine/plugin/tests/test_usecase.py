from __future__ import annotations

import io

import joblib
import pandas as pd
from ctsteps.contracts import UseCase
from ctsteps.steps.validate import check_frame

from automated_listing_engine import data, use_case


def test_implements_contract():
    assert isinstance(use_case, UseCase)
    assert set(use_case.models) == {"categorizer", "fraud"}


def test_data_is_reproducible_and_valid():
    a = use_case.ingest("categorizer", profile=None, seed=1, rows=500)
    b = use_case.ingest("categorizer", profile=None, seed=1, rows=500)
    pd.testing.assert_frame_equal(a, b)
    assert check_frame(a, use_case.schema("categorizer")) == []
    assert 0.05 < a["is_fraud"].mean() < 0.2


def test_drift_profile_moves_distributions():
    """The demo scenario: the drift profile must cross the retrain threshold (PSI > 0.3)."""
    from ctsteps.steps.drift import psi_by_column

    ref = use_case.ingest("fraud", profile=None, seed=2, rows=3000)
    same = use_case.ingest("fraud", profile=None, seed=5, rows=1000)
    cur = use_case.ingest("fraud", profile="drift", seed=3, rows=1000)
    quiet = psi_by_column(ref, same, ["price", "title_len"])
    drifted = psi_by_column(ref, cur, ["price", "title_len"])
    assert max(quiet.values()) < 0.2, quiet
    assert drifted["price"] > 0.3, drifted
    assert (cur["category"] == "electronics").mean() > (
        ref["category"] == "electronics"
    ).mean() + 0.15


def test_models_train_and_survive_plain_joblib():
    df = use_case.ingest("categorizer", profile=None, seed=4, rows=3000)
    for name in ("categorizer", "fraud"):
        est = use_case.build_model(name)
        est.fit(df[["title", "price"]], df[use_case.models[name].target])
        metrics = use_case.evaluate(name, est, df)
        assert metrics[use_case.models[name].primary_metric] > 0.7, metrics
        # round-trip through joblib as the serving runtime does
        buf = io.BytesIO()
        joblib.dump(est, buf)
        loaded = joblib.load(io.BytesIO(buf.getvalue()))
        # KServe v1 payload shape: one instance = dict of column -> list
        frame = pd.DataFrame({"title": ["iphone sealed"], "price": [420.0]})
        assert loaded.predict_proba(frame).shape[1] >= 2
    assert set(data.CATEGORIES) >= set(df["category"])
