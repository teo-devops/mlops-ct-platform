#!/usr/bin/env python3
"""Scaffold a use case: the paved road as one command.

    python3 scripts/repo/new-use-case.py <name> --models m1[,m2] [--task classification|regression]
                                         [--no-api] [--title "..."] [--dry-run]

It renders scripts/repo/use-case-template/ into use-cases/<name>/ (usecase.yaml, plugin, api,
the three charts, docs) and does every registration the platform needs — as DATA, in the places
the platform keeps data about use cases:
  * three workloads in group <name> (register-workload.py: AppProject + Application each)
  * the pipelines namespace in the argo-workflows module (values + manifests) and in the
    airflow module's RBAC
  * the use case's OWN artifact-store buckets and users, and its namespaces among the artifact store's clients
Then it runs validate-coherence.py. What is left is the use case's job: the four methods of
`UseCase`, the request schema of its API, its docs. The generated use case works as it is
(synthetic data), so `make secrets` + commit + `USE_CASE=<name> make build pipeline smoke drift`
close the loop on day one.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "scripts" / "repo" / "use-case-template"
USE_CASES = ROOT / "use-cases"
PLATFORM = ROOT / "gitops" / "environments" / "demo" / "platform"
STORE_VALUES = ROOT / "workloads" / "seaweedfs" / "values.yaml"
ARGO_WF_VALUES = PLATFORM / "argo-workflows" / "values.yaml"
ARGO_WF_NAMESPACES = PLATFORM / "argo-workflows" / "manifests" / "namespaces.yaml"
AIRFLOW_RBAC = PLATFORM / "airflow" / "manifests" / "rbac.yaml"
RX_NAME = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
RX_MODEL = re.compile(r"^[a-z][a-z0-9-]*$")
TASKS = {
    "classification": {
        "metric_imports": "accuracy_score, f1_score",
        "estimator": "LogisticRegression(max_iter=2000)",
        "estimator_import": "from sklearn.linear_model import LogisticRegression",
        "primary_metric": "f1_macro",
        "higher_is_better": "True",
        "evaluate": '{"f1_macro": float(f1_score(y, pred, average="macro")), "accuracy": float(accuracy_score(y, pred))}',
        "target_expr": 'np.where(signal + noise > np.median(signal), "yes", "no")',
        "target_dtype": "string",
        "predict_proba": "true",
        "prediction_sample": "[0.2, 0.8]",
    },
    "regression": {
        "metric_imports": "mean_absolute_error, r2_score",
        "estimator": "HistGradientBoostingRegressor(max_iter=200)",
        "estimator_import": "from sklearn.ensemble import HistGradientBoostingRegressor",
        "primary_metric": "mae",
        "higher_is_better": "False",
        "evaluate": '{"mae": float(mean_absolute_error(y, pred)), "r2": float(r2_score(y, pred))}',
        "target_expr": "signal + noise",
        "target_dtype": "number",
        "predict_proba": "false",
        "prediction_sample": "12.5",
    },
}


def title_of(name: str) -> str:
    return " ".join(w.capitalize() for w in name.split("-"))


def class_of(name: str) -> str:
    return "".join(w.capitalize() for w in name.split("-"))


def models_specs(models: list[str], task: dict) -> str:
    out = []
    for m in models:
        out.append(
            f'        "{m}": ModelSpec(\n'
            f'            name="{m}",\n'
            f'            target="{m}",\n'
            f"            features=FEATURES,\n"
            f'            primary_metric="{task["primary_metric"]}",\n'
            f"            higher_is_better={task['higher_is_better']},\n"
            f'            drift_columns=("x1", "x2", "zone"),\n'
            f"            min_improvement=0.0,\n"
            f"        ),"
        )
    return "\n".join(out)


def render_values(text: str, v: dict[str, str]) -> str:
    for k in sorted(v, key=len, reverse=True):
        text = text.replace(k, v[k])
    return text


def append_list_item(
    path: pathlib.Path, anchor: str, item: str, comment: str | None = None
) -> None:
    """Append `item` to the YAML list that starts at the line `anchor` (text-level, keeps comments)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.rstrip() == anchor)
    except StopIteration:
        sys.exit(f"{path.relative_to(ROOT)}: no line {anchor!r}")
    indent = len(lines[start]) - len(lines[start].lstrip()) + 2
    end = start + 1
    while end < len(lines) and (
        lines[end].startswith(" " * indent) or lines[end].strip() == ""
    ):
        end += 1
    while end > start + 1 and lines[end - 1].strip() == "":
        end -= 1
    if any(l.strip() == item.strip() for l in lines[start + 1 : end]):
        return
    new = ([" " * indent + comment] if comment else []) + [" " * indent + item]
    lines[end:end] = new
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_block(path: pathlib.Path, anchor: str, block: str) -> None:
    """Append an indented YAML block (several lines) under the list starting at `anchor`."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.rstrip() == anchor)
    except StopIteration:
        sys.exit(f"{path.relative_to(ROOT)}: no line {anchor!r}")
    indent = len(lines[start]) - len(lines[start].lstrip()) + 2
    end = start + 1
    while end < len(lines) and (
        lines[end].startswith(" " * indent) or lines[end].strip() == ""
    ):
        end += 1
    while end > start + 1 and lines[end - 1].strip() == "":
        end -= 1
    if block.splitlines()[0].strip() in {l.strip() for l in lines[start + 1 : end]}:
        return
    lines[end:end] = [" " * indent + l if l else l for l in block.splitlines()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("name", help="use case name (namespace-safe, e.g. delivery-eta)")
    ap.add_argument("--models", required=True, help="comma-separated model names")
    ap.add_argument("--task", choices=sorted(TASKS), default="classification")
    ap.add_argument(
        "--no-api", action="store_true", help="the use case only exposes models"
    )
    ap.add_argument("--title", help="human name (default: from the name)")
    ap.add_argument(
        "--dry-run", action="store_true", help="print what would be created"
    )
    args = ap.parse_args()

    name = args.name
    if not RX_NAME.match(name) or len(name) > 30:
        sys.exit(
            f"invalid name {name!r}: a short RFC 1123 name (namespaces are <name>-pipelines)"
        )
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models or any(not RX_MODEL.match(m) for m in models):
        sys.exit(f"invalid models {args.models!r}")
    dest = USE_CASES / name
    if dest.exists():
        sys.exit(f"{dest.relative_to(ROOT)} already exists")
    pkg = name.replace("-", "_")
    prefix = pkg.upper()
    title = args.title or title_of(name)
    task = TASKS[args.task]
    api = not args.no_api

    v = {
        "__UC__": name,
        "__UC_PKG__": pkg,
        "__UC_PREFIX__": prefix,
        "__UC_TITLE__": title,
        "__UC_CLASS__": class_of(name),
        "__MODELS_LIST__": "[" + ", ".join(models) + "]",
        "__MODELS_LIST_PY__": repr(models),
        "__MODELS_TUPLE__": "("
        + ", ".join(f'"{m}"' for m in models)
        + ("," if len(models) == 1 else "")
        + ")",
        "__MODELS_VERSIONS__": "\n".join(f'  {m}:\n    version: "0"' for m in models),
        "__MODELS_SERVING__": "\n".join(
            f'  {m}:\n    version: "0"\n    minReplicas: 1\n    maxReplicas: 1'
            for m in models
        ),
        "__MODELS_SPECS__": models_specs(models, task),
        "__MODELS_PROSE__": " and ".join(f"`{m}`" for m in models),
        "__MODELS_TABLE__": "\n".join(
            f"| `{m}` | `{m}` | x1, x2, x3, zone | `{task['primary_metric']}` | x1, x2, zone |"
            for m in models
        ),
        "__METRIC_IMPORTS__": task["metric_imports"],
        "__ESTIMATOR_IMPORT__": task["estimator_import"],
        "__ESTIMATOR__": task["estimator"],
        "__EVALUATE_EXPR__": task["evaluate"],
        "__TARGET_EXPR__": task["target_expr"],
        "__TARGET_DTYPE__": task["target_dtype"],
        "__PREDICT_PROBA__": task["predict_proba"],
        "__PREDICTION_SAMPLE__": task["prediction_sample"],
        "__API_ENABLED__": "true" if api else "false",
    }

    if args.dry_run:
        print(
            f"would create use-cases/{name}/ (package {pkg}, models {models}, task {args.task}, api={api})"
        )
        return 0

    # 1. render the template
    for src in sorted(TEMPLATE.rglob("*")):
        rel = pathlib.Path(render_values(str(src.relative_to(TEMPLATE)), v))
        if (
            not api
            and rel.parts[0] in ("api",)
            or (not api and rel.parts[:2] == ("workloads", "api"))
        ):
            continue
        dst = dest / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = render_values(src.read_text(encoding="utf-8"), v)
        dst.write_text(text, encoding="utf-8")
    (dest / "plugin" / "src" / pkg).mkdir(parents=True, exist_ok=True)
    print(f"✓ use-cases/{name}/ rendered from the template")

    # 2. register the workloads (AppProject + Application each, wired into the group)
    reg = ROOT / "scripts" / "repo" / "register-workload.py"
    workloads = [("serving", "stateless"), ("pipelines", "pipeline")] + (
        [("api", "stateless")] if api else []
    )
    for wl, arch in workloads:
        subprocess.run(
            [
                sys.executable,
                str(reg),
                f"{name}-{wl}",
                f"use-cases/{name}/workloads/{wl}",
                "--group",
                name,
                "--archetype",
                arch,
                "--description",
                f"{title} use case — {wl} workload, confined to its namespace.",
                "--no-validate",
            ],
            check=True,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
        )
    if api:
        app = (
            ROOT
            / "gitops"
            / "environments"
            / "demo"
            / "apps"
            / name
            / f"{name}-api.yaml"
        )
        text = app.read_text(encoding="utf-8")
        text = text.replace(
            "  syncPolicy:\n",
            "  # Progressive delivery (opt-in): the Rollouts controller stamps this selector.\n"
            "  ignoreDifferences:\n    - group: ''\n      kind: Service\n      jqPathExpressions:\n"
            '        - .spec.selector."rollouts-pod-template-hash"\n    - group: argoproj.io\n      kind: Rollout\n'
            "      jsonPointers:\n        - /metadata/annotations/rollout.argoproj.io~1revision\n\n  syncPolicy:\n",
            1,
        )
        text = text.replace(
            "      - ServerSideApply=true\n",
            "      - ServerSideApply=true\n      - RespectIgnoreDifferences=true\n",
            1,
        )
        text = re.sub(
            r"      prune: false",
            "      prune: true   # stateless: Deployment <-> Rollout switches must remove the retired one",
            text,
            count=1,
        )
        app.write_text(text, encoding="utf-8")
    print(f"✓ workloads registered in group {name!r}")

    # 3. the platform data that names a use case
    ns_p = f"{name}-pipelines"
    append_list_item(ARGO_WF_VALUES, "  workflowNamespaces:", f"- {ns_p}")
    with ARGO_WF_NAMESPACES.open("a", encoding="utf-8") as fh:
        fh.write(
            f"---\napiVersion: v1\nkind: Namespace\nmetadata:\n  name: {ns_p}\n  labels:\n"
            f'    app.kubernetes.io/managed-by: argocd\n    mlops-ct-platform.dev/workflow-namespace: "true"\n'
        )
    if AIRFLOW_RBAC.exists():
        rbac = AIRFLOW_RBAC.read_text(encoding="utf-8")
        first = rbac.index("apiVersion: rbac.authorization.k8s.io/v1")
        pair = rbac[first:].replace("automated-listing-engine-pipelines", ns_p)
        AIRFLOW_RBAC.write_text(rbac.rstrip("\n") + "\n---\n" + pair, encoding="utf-8")
    for suffix in ("models", "datasets", "predictions"):
        append_list_item(
            STORE_VALUES,
            "buckets:",
            f"- {name}-{suffix}",
            comment=f"# --- use case: {name}" if suffix == "models" else None,
        )
    append_block(
        STORE_VALUES,
        "users:",
        f"# --- use case: {name}\n- name: {name}-reader\n  envPrefix: {prefix}_READER\n  policy:\n    ro: [{name}-models]\n"
        f"- name: {name}-pipeline\n  envPrefix: {prefix}_PIPELINE\n  policy:\n    rw: [{name}-models, {name}-datasets, mlflow]\n    ro: [{name}-predictions]\n"
        f"- name: {name}-api\n  envPrefix: {prefix}_API\n  policy:\n    wo: [{name}-predictions]",
    )
    for i, wl in enumerate(["serving", "pipelines"] + (["api"] if api else [])):
        append_list_item(
            STORE_VALUES,
            "  apiClients:",
            f"- {name}-{wl}",
            comment=f"# --- use case: {name}" if i == 0 else None,
        )
    print(
        "✓ platform data updated: argo-workflows namespaces, airflow RBAC, artifact-store buckets/users/clients"
    )

    # 4. coherence
    code = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "repo" / "validate-coherence.py")],
        cwd=ROOT,
        check=False,
    ).returncode
    print(f"""
Next, in use-cases/{name}/:
  1. plugin/src/{pkg}/data.py     real ingest (or keep the synthetic data to try the loop)
     plugin/src/{pkg}/usecase.py  the four methods: ingest, schema, build_model, evaluate
  2. api/app/schemas.py           the real request; usecase.yaml `api.sample` accordingly
  3. make venv && make validate   (tests of the plugin and the API run on the platform harness)
  4. make secrets; git add -A && git commit; git push   (Argo CD creates the three workloads)
  5. USE_CASE={name} make build pipeline smoke drift
""")
    return code


if __name__ == "__main__":
    sys.exit(main())
