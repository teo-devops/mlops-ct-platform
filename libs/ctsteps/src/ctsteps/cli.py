"""`ctsteps <step> ...` — the command line every orchestrator adapter calls."""

from __future__ import annotations

import argparse
import json
import os
import sys

from ctsteps.steps import drift, evaluate, ingest, preprocess, promote, register, train, validate
from ctsteps.steps.common import Context


def _common(p: argparse.ArgumentParser, run_id: bool = True) -> None:
    p.add_argument(
        "--use-case",
        default=os.environ.get("CT_USE_CASE"),
        help="module:attr implementing UseCase (env CT_USE_CASE)",
    )
    p.add_argument("--model", required=True, help="model name within the use case")
    if run_id:
        p.add_argument(
            "--run-id",
            default=os.environ.get("CT_RUN_ID"),
            required="CT_RUN_ID" not in os.environ,
            help="pipeline run id: names the dataset folder (env CT_RUN_ID)",
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ctsteps", description=__doc__)
    sub = p.add_subparsers(dest="step", required=True)

    s = sub.add_parser("ingest", help="raw dataset -> artifact store")
    _common(s)
    # Data profile of the use case: explicit flag > per-run override (orchestrator
    # parameter) > data-source state (CT_DATA_PROFILE, e.g. a ConfigMap that
    # represents "what the upstream data platform delivers now").
    s.add_argument(
        "--profile",
        default=os.environ.get("CT_DATA_PROFILE_OVERRIDE")
        or os.environ.get("CT_DATA_PROFILE")
        or None,
    )
    s.add_argument("--seed", type=int, default=int(os.environ.get("CT_SEED", "42")))
    s.add_argument("--rows", type=int, default=int(os.environ.get("CT_ROWS", "6000")))

    # `sample` is not a pipeline step: it prints feature records of the use
    # case's data (any profile) as JSON, so that platform scripts can generate
    # realistic traffic for an API without knowing the use case's columns.
    s = sub.add_parser("sample", help="print feature records as JSON (traffic generator)")
    _common(s, run_id=False)
    s.add_argument("--profile", default=None)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--rows", type=int, default=100)

    s = sub.add_parser("validate", help="data-quality gate")
    _common(s)

    s = sub.add_parser("preprocess", help="split + freeze reference")
    _common(s)
    s.add_argument("--holdout-ratio", type=float, default=0.25)
    s.add_argument("--seed", type=int, default=int(os.environ.get("CT_SEED", "42")))
    s.add_argument("--reference-rows", type=int, default=2000)

    s = sub.add_parser("train", help="fit + log run")
    _common(s)
    s.add_argument("--trigger", default=os.environ.get("CT_TRIGGER", "manual"))

    s = sub.add_parser("evaluate", help="champion/challenger gate")
    _common(s)
    s.add_argument("--mlflow-run-id", required=True)

    s = sub.add_parser("register", help="version + serving artefact")
    _common(s)
    s.add_argument("--mlflow-run-id", required=True)

    s = sub.add_parser("promote", help="alias champion + GitOps bump")
    _common(s)
    s.add_argument("--version", type=int, required=True)
    s.add_argument("--trigger", default=os.environ.get("CT_TRIGGER", "manual"))
    s.add_argument("--dry-run", action="store_true")

    s = sub.add_parser("drift", help="PSI reference vs live, push metrics, retrain")
    _common(s, run_id=False)
    s.add_argument(
        "--window-minutes", type=int, default=int(os.environ.get("CT_DRIFT_WINDOW_MINUTES", "30"))
    )
    s.add_argument("--warn", type=float, default=float(os.environ.get("CT_DRIFT_WARN", "0.2")))
    s.add_argument(
        "--retrain", type=float, default=float(os.environ.get("CT_DRIFT_RETRAIN", "0.3"))
    )
    s.add_argument("--min-rows", type=int, default=int(os.environ.get("CT_DRIFT_MIN_ROWS", "200")))
    s.add_argument(
        "--pushgateway",
        default=os.environ.get(
            "CT_PUSHGATEWAY", "pushgateway.observability.svc.cluster.local:9091"
        ),
    )
    s.add_argument("--workflow-template", default=os.environ.get("CT_WORKFLOW_TEMPLATE", ""))
    # where the live window comes from: the prediction log on the artifact store
    # (default) or the event-bus topic (docs/modules/event-bus.md)
    s.add_argument(
        "--source", choices=["s3", "kafka"], default=os.environ.get("CT_DRIFT_SOURCE", "s3")
    )
    s.add_argument("--bootstrap", default=os.environ.get("CT_EVENT_BUS_BOOTSTRAP", ""))
    s.add_argument("--topic", default=os.environ.get("CT_EVENT_BUS_TOPIC", "predictions"))
    s.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = Context.build(args.use_case, args.model, getattr(args, "run_id", "monitor"))
    if args.step == "sample":
        frame = ctx.use_case.ingest(
            args.model, profile=args.profile, seed=args.seed, rows=args.rows
        )
        records = frame[list(ctx.spec.features)].to_dict(orient="records")
        json.dump(records, sys.stdout, default=str)
        return 0
    if args.step == "ingest":
        ingest.run(ctx, profile=args.profile, seed=args.seed, rows=args.rows)
    elif args.step == "validate":
        validate.run(ctx)
    elif args.step == "preprocess":
        preprocess.run(
            ctx,
            holdout_ratio=args.holdout_ratio,
            seed=args.seed,
            reference_rows=args.reference_rows,
        )
    elif args.step == "train":
        train.run(ctx, trigger=args.trigger)
    elif args.step == "evaluate":
        evaluate.run(ctx, mlflow_run_id=args.mlflow_run_id)
    elif args.step == "register":
        register.run(ctx, mlflow_run_id=args.mlflow_run_id)
    elif args.step == "promote":
        promote.run(ctx, version=args.version, trigger=args.trigger, dry_run=args.dry_run)
    elif args.step == "drift":
        drift.run(
            ctx,
            source=args.source,
            bootstrap=args.bootstrap,
            topic=args.topic,
            window_minutes=args.window_minutes,
            warn=args.warn,
            retrain=args.retrain,
            min_rows=args.min_rows,
            pushgateway=args.pushgateway,
            workflow_template=args.workflow_template,
            dry_run=args.dry_run,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
