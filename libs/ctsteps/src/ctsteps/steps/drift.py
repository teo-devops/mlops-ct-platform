"""drift — the model-monitoring contract: detect silent failure, act on it.

A model that returns 200s but is quietly wrong shows no error rate; only the
distributions give it away. This step compares the training reference of the
champion with the live prediction log over a window, per column and for the
prediction itself (Population Stability Index via Evidently), publishes the
result as Prometheus metrics, and — above the retrain threshold — submits the
training pipeline through the orchestrator adapter.

Policy (from the reference document): PSI < 0.2 nothing · 0.2–0.3 warn ·
> 0.3 retrain. The thresholds are parameters; the policy is a contract.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset
from mlflow import MlflowClient
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

from ctsteps import io_s3, registry, result
from ctsteps.steps.common import Context

PREDICTION_COLUMN = "prediction"


def psi_by_column(
    reference: pd.DataFrame, current: pd.DataFrame, columns: list[str]
) -> dict[str, float]:
    """PSI per column (Evidently, method=psi). Booleans and strings are categorical."""
    reference = reference[columns].copy()
    current = current[columns].copy()
    numerical, categorical = [], []
    for c in columns:
        if pd.api.types.is_bool_dtype(reference[c]) or not pd.api.types.is_numeric_dtype(
            reference[c]
        ):
            categorical.append(c)
            reference[c] = reference[c].astype(str)
            current[c] = current[c].astype(str)
        else:
            numerical.append(c)
            current[c] = pd.to_numeric(current[c], errors="coerce")
    dd = DataDefinition(numerical_columns=numerical, categorical_columns=categorical)
    report = Report([DataDriftPreset(method="psi", columns=columns)])
    snapshot = report.run(
        Dataset.from_pandas(current, data_definition=dd),
        Dataset.from_pandas(reference, data_definition=dd),
    )
    out: dict[str, float] = {}
    for m in snapshot.dict()["metrics"]:
        cfg = m.get("config", {})
        if cfg.get("type", "").endswith("ValueDrift"):
            out[cfg["column"]] = float(m["value"])
    return out


def push_metrics(
    gateway: str,
    use_case: str,
    model: str,
    psi: dict[str, float],
    detected: bool,
    rows: int,
    warn: float,
    retrain: float,
) -> None:
    reg = CollectorRegistry()
    labels = {"use_case": use_case, "model": model}
    g_psi = Gauge(
        "ct_drift_psi",
        "PSI between training reference and live window",
        ["use_case", "model", "column"],
        registry=reg,
    )
    for col, v in psi.items():
        g_psi.labels(column=col, **labels).set(v)
    Gauge(
        "ct_drift_detected",
        "1 when the retrain threshold was exceeded in the last run",
        list(labels),
        registry=reg,
    ).labels(**labels).set(1 if detected else 0)
    Gauge(
        "ct_drift_window_rows", "Predictions in the analysed window", list(labels), registry=reg
    ).labels(**labels).set(rows)
    Gauge(
        "ct_drift_last_run_timestamp_seconds",
        "When the monitor last ran",
        list(labels),
        registry=reg,
    ).labels(**labels).set(time.time())
    Gauge("ct_drift_threshold_warn", "Warn threshold", list(labels), registry=reg).labels(
        **labels
    ).set(warn)
    Gauge("ct_drift_threshold_retrain", "Retrain threshold", list(labels), registry=reg).labels(
        **labels
    ).set(retrain)
    push_to_gateway(gateway, job="ct-drift", grouping_key=labels, registry=reg)


def submit_retrain(ctx: Context, workflow_template: str, namespace: str) -> str | None:
    """Orchestrator adapter (Argo Workflows): one Workflow from the template, unless one is running."""
    from kubernetes import client, config

    config.load_incluster_config()
    api = client.CustomObjectsApi()
    group, version, plural = "argoproj.io", "v1alpha1", "workflows"
    running = api.list_namespaced_custom_object(
        group,
        version,
        namespace,
        plural,
        label_selector=f"ct.mlops/model={ctx.spec.name},ct.mlops/use-case={ctx.use_case.name}",
    )
    for wf in running.get("items", []):
        phase = wf.get("status", {}).get("phase", "")
        if phase in ("", "Pending", "Running"):
            return None
    body = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "generateName": f"ct-{ctx.spec.name}-drift-",
            "labels": {
                "ct.mlops/model": ctx.spec.name,
                "ct.mlops/use-case": ctx.use_case.name,
                "ct.mlops/trigger": "drift",
            },
        },
        "spec": {
            "workflowTemplateRef": {"name": workflow_template},
            "arguments": {
                "parameters": [
                    {"name": "model", "value": ctx.spec.name},
                    {"name": "trigger", "value": "drift"},
                ]
            },
        },
    }
    created = api.create_namespaced_custom_object(group, version, namespace, plural, body)
    return created["metadata"]["name"]


def run(
    ctx: Context,
    *,
    window_minutes: int,
    warn: float,
    retrain: float,
    min_rows: int,
    pushgateway: str,
    workflow_template: str,
    dry_run: bool,
) -> dict:
    registry.setup(ctx.settings.mlflow_tracking_uri, ctx.use_case.name, ctx.spec.name)
    client = MlflowClient()
    name = registry.registered_name(ctx.use_case.name, ctx.spec.name)
    champ = registry.champion_version(client, name)
    if champ is None:
        return result.write(ctx.settings.outputs_dir, skipped="no champion yet")
    reference_uri = champ.tags.get("reference_uri")
    if not reference_uri:
        return result.write(ctx.settings.outputs_dir, skipped="champion has no reference_uri tag")
    reference = io_s3.get_parquet(ctx.s3, reference_uri)

    since = datetime.now(UTC) - timedelta(minutes=window_minutes)
    uris = [u for u, _ in io_s3.list_objects(ctx.s3, ctx.predictions_prefix(), newer_than=since)]
    current = io_s3.read_jsonl(ctx.s3, uris) if uris else pd.DataFrame()
    # Only predictions made by the champion count: a just-promoted version
    # must not be judged on traffic served by its predecessor.
    if len(current) and "model_version" in current.columns:
        current = current[current["model_version"].astype(str) == str(champ.version)]
    rows = len(current)
    columns = [c for c in ctx.spec.drift_columns if c in reference.columns and c in current.columns]
    if rows < min_rows or not columns:
        push_metrics(
            pushgateway, ctx.use_case.name, ctx.spec.name, {}, False, rows, warn, retrain
        ) if not dry_run else None
        return result.write(
            ctx.settings.outputs_dir,
            skipped=f"{rows} rows < {min_rows} or no comparable columns",
            rows=rows,
        )

    # The prediction distribution: the reference has the target, live traffic
    # has the model's output for it.
    if ctx.spec.target in reference.columns and PREDICTION_COLUMN in current.columns:
        reference = reference.rename(columns={ctx.spec.target: PREDICTION_COLUMN})
        columns = columns + [PREDICTION_COLUMN]

    psi = psi_by_column(reference, current, columns)
    worst = max(psi.values()) if psi else 0.0
    detected = worst > retrain
    level = "retrain" if detected else "warn" if worst > warn else "ok"
    submitted = None
    if not dry_run:
        push_metrics(
            pushgateway, ctx.use_case.name, ctx.spec.name, psi, detected, rows, warn, retrain
        )
        if detected and workflow_template:
            submitted = submit_retrain(
                ctx, workflow_template, os.environ.get("CT_NAMESPACE", "default")
            )
    return result.write(
        ctx.settings.outputs_dir,
        level=level,
        max_psi=round(worst, 4),
        psi=psi,
        rows=rows,
        window_minutes=window_minutes,
        champion_version=int(champ.version),
        retrain_submitted=submitted or "",
    )
