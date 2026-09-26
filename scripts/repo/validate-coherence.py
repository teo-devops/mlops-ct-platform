#!/usr/bin/env python3
"""Checks that the GitOps tree is coherent before it reaches the cluster.

Registering a workload is copy-paste-replace on two files; the likely error is
a marker left behind or a name that does not match between AppProject and
Application. Argo CD detects it — it refuses the sync — but in the cluster,
after the merge. This detects it in the PR.

    Usage:  python3 scripts/repo/validate-coherence.py
    Exit code 1 on any incoherence.

Inherited from teo-devops/Argo-cd-Labs scripts/validar-coherencia.py and
extended for this repository: monorepo (every workload reads the platform
repository) and platform modules (upstream charts under project `platform`).
"""

from __future__ import annotations

import pathlib
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML missing:  pip install pyyaml")

ROOT = pathlib.Path(__file__).resolve().parents[2]  # scripts/repo/<this> -> repo root
GITOPS = ROOT / "gitops"
ENV = GITOPS / "environments" / "demo"
DIR_PROJECTS = ENV / "projects"
DIR_APPS = ENV / "apps"
DIR_PLATFORM = ENV / "platform"
INSTALL_SH = ROOT / "scripts" / "platform" / "04-install.sh"
ENGINE_APP = ENV / "argo-cd.yaml"
ROOT_APP = GITOPS / "bootstrap" / "root-app.yaml"
EXPECTED_SERVER = "https://kubernetes.default.svc"
ARCHETYPES = {"stateless", "batch", "stateful", "pipeline"}
ARCHETYPE_ANNOTATION = "mlops-ct-platform.dev/archetype"
MARKERS = ("NAME", "REPO_URL", "DESCRIPTION", "GROUP", "TEAM", "ARCHETYPE", "PATH")
PLATFORM_PROJECTS = {"platform"}
DIR_USE_CASES = ROOT / "use-cases"
STORE_VALUES = ROOT / "workloads" / "seaweedfs" / "values.yaml"
ARGO_WF_VALUES = DIR_PLATFORM / "argo-workflows" / "values.yaml"
ARGO_WF_NAMESPACES = DIR_PLATFORM / "argo-workflows" / "manifests" / "namespaces.yaml"
AIRFLOW_RBAC = DIR_PLATFORM / "airflow" / "manifests" / "rbac.yaml"
UC_TEMPLATE = ROOT / "scripts" / "repo" / "use-case-template"

errors: list[str] = []


def error(msg: str) -> None:
    errors.append(msg)


def load(path: pathlib.Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def resources_of(kustomization: pathlib.Path) -> set[str]:
    return set(load(kustomization).get("resources", []))


def yaml_files(directory: pathlib.Path) -> list[pathlib.Path]:
    """Manifests directly in `directory` and in its group subdirectories."""
    return sorted(
        p for p in directory.glob("**/*.yaml") if p.name != "kustomization.yaml"
    )


def commented_resources(kustomization: pathlib.Path) -> set[str]:
    """Entries kept as `#  - <name>`: declared, deliberately not deployed (opt-in)."""
    return set(re.findall(r"^\s*#\s*-\s*([a-z0-9.-]+)\s*$", kustomization.read_text(encoding="utf-8"), re.MULTILINE))


def check_kustomize_wiring(directory: pathlib.Path) -> None:
    """Every file must be reachable: root kustomization -> group -> file (or opt-in, commented)."""
    root_listed = resources_of(directory / "kustomization.yaml") | commented_resources(directory / "kustomization.yaml")
    for group in sorted(d for d in directory.iterdir() if d.is_dir()):
        if group.name not in root_listed:
            error(
                f"{rel(directory)}/kustomization.yaml: group {group.name!r} exists but is not listed"
            )
        kz = group / "kustomization.yaml"
        if not kz.exists():
            error(f"{rel(group)}: no kustomization.yaml")
            continue
        listed = resources_of(kz)
        for f in sorted(group.glob("*.yaml")):
            if f.name != "kustomization.yaml" and f.name not in listed:
                error(f"{rel(kz)}: {f.name} missing; the manifest is not applied")
    for f in sorted(directory.glob("*.yaml")):
        if f.name != "kustomization.yaml" and f.name not in root_listed:
            error(
                f"{rel(directory)}/kustomization.yaml: {f.name} missing; the manifest is not applied"
            )


def sources_of(spec: dict) -> list[dict]:
    if spec.get("sources"):
        return [s for s in spec["sources"] if isinstance(s, dict)]
    if spec.get("source"):
        return [spec["source"]]
    return []


def scalars(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for k, v in node.items() for s in scalars(k) + scalars(v)]
    if isinstance(node, list):
        return [s for v in node for s in scalars(v)]
    return []


def rel(p: pathlib.Path) -> str:
    return str(p.relative_to(ROOT))


def check_template_markers() -> None:
    """No marker of gitops/templates/ may survive in an environment (values, not comments)."""
    for directory in (DIR_PROJECTS, DIR_APPS):
        for path in yaml_files(directory):
            for value in scalars(load(path)):
                for marker in MARKERS:
                    if re.search(rf"(?<![\w-]){marker}(?![\w-])", value):
                        error(
                            f"{rel(path)}: template marker {marker!r} left in value {value!r}"
                        )


def check_chart_version() -> None:
    """install.sh and argo-cd.yaml must pin the same Argo CD chart version."""
    m = re.search(
        r'^CHART_VERSION="([^"]+)"',
        INSTALL_SH.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not m:
        error(f"{rel(INSTALL_SH)}: CHART_VERSION not found")
        return
    sources = (load(ENGINE_APP).get("spec") or {}).get("sources") or []
    chart = next((s for s in sources if s.get("chart") == "argo-cd"), None)
    if chart is None:
        error(f"{rel(ENGINE_APP)}: no source with chart 'argo-cd'")
        return
    if m.group(1) != chart.get("targetRevision"):
        error(
            f"argo-cd chart version differs: install.sh {m.group(1)!r} vs "
            f"{rel(ENGINE_APP)} {chart.get('targetRevision')!r}"
        )


def check_platform_repo() -> None:
    """lib.sh (credential), root-app and the engine must point at the same repo."""
    lib = ROOT / "scripts" / "lib.sh"
    m = re.search(
        r'^PLATFORM_REPO="([^"]+)"', lib.read_text(encoding="utf-8"), re.MULTILINE
    )
    if not m:
        error(f"{rel(lib)}: PLATFORM_REPO not found")
        return
    url_root = ((load(ROOT_APP).get("spec") or {}).get("source") or {}).get("repoURL")
    if m.group(1) != url_root:
        error(
            f"PLATFORM_REPO in lib.sh ({m.group(1)!r}) != repoURL of {rel(ROOT_APP)} ({url_root!r})"
        )
    ref = next(
        (s for s in sources_of(load(ENGINE_APP).get("spec", {})) if s.get("ref")), {}
    )
    if ref.get("repoURL") != url_root:
        error(
            f"{rel(ENGINE_APP)}: $values source repoURL ({ref.get('repoURL')!r}) != root-app repoURL"
        )


def check_platform_modules(projects: dict[str, dict]) -> None:
    """Every module directory is listed, uses project `platform` and allowed repos."""
    kustomization = DIR_PLATFORM / "kustomization.yaml"
    listed = resources_of(kustomization)
    # Opt-in modules: a complete directory whose line is commented out (`#  - <name>`).
    # Still validated in full; only the "not listed" check is waived.
    opt_in = commented_resources(kustomization)
    pspec = projects.get("platform", {}).get("spec", {})
    allowed = pspec.get("sourceRepos", [])
    for module in sorted(d for d in DIR_PLATFORM.iterdir() if d.is_dir()):
        if module.name not in listed and module.name not in opt_in:
            error(
                f"gitops/environments/demo/platform/kustomization.yaml: module {module.name!r} exists but is not listed (disabled?)"
            )
        app = module / "application.yaml"
        if not app.exists():
            error(f"{rel(module)}: no application.yaml")
            continue
        doc = load(app)
        if doc.get("kind") != "Application":
            error(f"{rel(app)}: expected kind Application")
            continue
        name = doc.get("metadata", {}).get("name")
        if name != module.name:
            error(f"{rel(app)}: metadata.name {name!r} != directory {module.name!r}")
        spec = doc.get("spec", {})
        if spec.get("project") != "platform":
            error(
                f"{rel(app)}: platform modules must use project 'platform' (found {spec.get('project')!r})"
            )
        for src in sources_of(spec):
            if src.get("repoURL") not in allowed:
                error(
                    f"{rel(app)}: repoURL {src.get('repoURL')!r} not in platform sourceRepos"
                )
            for vf in (src.get("helm") or {}).get("valueFiles") or []:
                if vf.startswith("$values/"):
                    target = ROOT / vf[len("$values/") :]
                    if not target.exists():
                        error(f"{rel(app)}: values file {vf!r} does not exist")
            if src.get("path") and src.get("repoURL", "").endswith(
                "mlops-ct-platform.git"
            ):
                if not (ROOT / src["path"]).exists():
                    error(
                        f"{rel(app)}: path {src['path']!r} does not exist in the repo"
                    )
        if "argocd.argoproj.io/sync-wave" not in (
            doc.get("metadata", {}).get("annotations") or {}
        ):
            error(f"{rel(app)}: platform modules must declare a sync-wave")


def use_cases() -> dict[str, dict]:
    """Every use case declared by a usecase.yaml (directories starting with `_` are templates)."""
    found = {}
    if not DIR_USE_CASES.exists():
        return found
    for f in sorted(DIR_USE_CASES.glob("*/usecase.yaml")):
        if f.parent.name.startswith("_"):
            continue
        found[f.parent.name] = load(f)
    return found


def check_use_cases() -> None:
    """A use case is declared once (usecase.yaml), wired everywhere the platform keeps data
    about it, consistent with its own charts — and isolated: it never names another use case."""
    ucs = use_cases()
    if not ucs:
        return
    store = load(STORE_VALUES)
    buckets = set(store.get("buckets") or [])
    users = {u["name"]: u for u in store.get("users") or []}
    api_clients = set((store.get("networkPolicy") or {}).get("apiClients") or [])
    wf_namespaces = set(
        (load(ARGO_WF_VALUES).get("controller") or {}).get("workflowNamespaces") or []
    )
    with ARGO_WF_NAMESPACES.open(encoding="utf-8") as fh:
        declared_ns = {d["metadata"]["name"] for d in yaml.safe_load_all(fh) if d}
    airflow_ns = set()
    if AIRFLOW_RBAC.exists():
        with AIRFLOW_RBAC.open(encoding="utf-8") as fh:
            airflow_ns = {
                d["metadata"]["namespace"] for d in yaml.safe_load_all(fh) if d
            }
    deployed_groups = resources_of(DIR_APPS / "kustomization.yaml")
    apps = {p.stem: p.parent.name for p in yaml_files(DIR_APPS)}
    archetype_of = {
        p.stem: (load(p).get("metadata", {}).get("annotations") or {}).get(
            ARCHETYPE_ANNOTATION
        )
        for p in yaml_files(DIR_APPS)
    }

    for uc, decl in ucs.items():
        d = DIR_USE_CASES / uc
        r = f"use-cases/{uc}"
        if decl.get("name") != uc:
            error(f"{r}/usecase.yaml: name {decl.get('name')!r} != directory {uc!r}")
        pkg = decl.get("package", "")
        models = decl.get("models") or []
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", pkg):
            error(f"{r}/usecase.yaml: package {pkg!r} is not a python package name")
        if not models:
            error(f"{r}/usecase.yaml: no models")
        api_enabled = bool((decl.get("api") or {}).get("enabled"))
        # 1. its workloads, registered in its own group with the right archetypes
        expected = {f"{uc}-serving": "stateless", f"{uc}-pipelines": "pipeline"}
        if api_enabled:
            expected[f"{uc}-api"] = "stateless"
        if uc not in deployed_groups and uc not in commented_resources(DIR_APPS / "kustomization.yaml"):
            error(f"{r}: group {uc!r} neither listed nor opt-in in apps/kustomization.yaml")
        if (uc in deployed_groups) != (uc in resources_of(DIR_PROJECTS / "kustomization.yaml")):
            error(f"{r}: group {uc!r} must be enabled (or opt-in) in BOTH apps/ and projects/ kustomizations")
        for wl, arch in expected.items():
            if apps.get(wl) != uc:
                error(
                    f"{r}: workload {wl!r} not registered in group {uc!r} (scripts/repo/register-workload.py)"
                )
            elif archetype_of.get(wl) != arch:
                error(
                    f"{r}: workload {wl!r} archetype {archetype_of.get(wl)!r}, expected {arch!r}"
                )
        # 2. the platform data that names it
        ns_p = f"{uc}-pipelines"
        if ns_p not in wf_namespaces:
            error(
                f"{rel(ARGO_WF_VALUES)}: {ns_p!r} missing in controller.workflowNamespaces"
            )
        if ns_p not in declared_ns:
            error(f"{rel(ARGO_WF_NAMESPACES)}: Namespace {ns_p!r} missing")
        if AIRFLOW_RBAC.exists() and ns_p not in airflow_ns:
            error(f"{rel(AIRFLOW_RBAC)}: no Role/RoleBinding for {ns_p!r}")
        for b in (f"{uc}-models", f"{uc}-datasets", f"{uc}-predictions"):
            if b not in buckets:
                error(
                    f"{rel(STORE_VALUES)}: bucket {b!r} missing (isolation: one set of buckets per use case)"
                )
        prefix = uc.upper().replace("-", "_")
        for user, env, must in (
            (f"{uc}-reader", f"{prefix}_READER", {f"{uc}-models"}),
            (
                f"{uc}-pipeline",
                f"{prefix}_PIPELINE",
                {f"{uc}-models", f"{uc}-datasets", f"{uc}-predictions", "mlflow"},
            ),
            (f"{uc}-api", f"{prefix}_API", {f"{uc}-predictions"}),
        ):
            u = users.get(user)
            if not u:
                error(
                    f"{rel(STORE_VALUES)}: user {user!r} missing (isolation: one set of users per use case)"
                )
                continue
            if u.get("envPrefix") != env:
                error(
                    f"{rel(STORE_VALUES)}: user {user!r} envPrefix {u.get('envPrefix')!r}, expected {env!r}"
                )
            granted = {b for v in (u.get("policy") or {}).values() for b in v}
            if granted != must:
                error(
                    f"{rel(STORE_VALUES)}: user {user!r} touches {sorted(granted)}; a use case's user may only touch {sorted(must)}"
                )
        for ns in expected:
            if ns not in api_clients:
                error(
                    f"{rel(STORE_VALUES)}: {ns!r} missing in networkPolicy.apiClients"
                )
        # 3. its charts agree with the declaration
        charts = d / "workloads"
        pv = (
            load(charts / "pipelines" / "values.yaml")
            if (charts / "pipelines" / "values.yaml").exists()
            else {}
        )
        sv = (
            load(charts / "serving" / "values.yaml")
            if (charts / "serving" / "values.yaml").exists()
            else {}
        )
        av = (
            load(charts / "api" / "values.yaml")
            if (charts / "api" / "values.yaml").exists()
            else {}
        )
        if (
            pv.get("useCase") != uc
            or sv.get("useCase") != uc
            or (api_enabled and av.get("useCase") != uc)
        ):
            error(f"{r}/workloads: every chart must set useCase: {uc}")
        if pv.get("useCaseRef") != f"{pkg}:use_case":
            error(
                f"{r}/workloads/pipelines/values.yaml: useCaseRef must be {pkg}:use_case"
            )
        if sorted(pv.get("models") or []) != sorted(models):
            error(
                f"{r}/workloads/pipelines/values.yaml: models {pv.get('models')} != usecase.yaml {models}"
            )
        if sorted((sv.get("models") or {}).keys()) != sorted(models):
            error(
                f"{r}/workloads/serving/values.yaml: models {sorted((sv.get('models') or {}).keys())} != usecase.yaml {models}"
            )
        store = pv.get("artifactStore") or {}
        for key, b in (
            ("datasetsBucket", f"{uc}-datasets"),
            ("modelsBucket", f"{uc}-models"),
            ("predictionsBucket", f"{uc}-predictions"),
        ):
            if store.get(key) != b:
                error(
                    f"{r}/workloads/pipelines/values.yaml: artifactStore.{key} must be {b}"
                )
        if (sv.get("artifactStore") or {}).get("bucket") != f"{uc}-models":
            error(
                f"{r}/workloads/serving/values.yaml: artifactStore.bucket must be {uc}-models"
            )
        if (sv.get("networkPolicy") or {}).get("apiNamespace") != f"{uc}-api":
            error(
                f"{r}/workloads/serving/values.yaml: networkPolicy.apiNamespace must be {uc}-api"
            )
        if api_enabled:
            if (av.get("serving") or {}).get("namespace") != f"{uc}-serving":
                error(
                    f"{r}/workloads/api/values.yaml: serving.namespace must be {uc}-serving"
                )
            if (av.get("predictionLog") or {}).get("bucket") != f"{uc}-predictions":
                error(
                    f"{r}/workloads/api/values.yaml: predictionLog.bucket must be {uc}-predictions"
                )
            if sorted((av.get("models") or {}).keys()) != sorted(models):
                error(
                    f"{r}/workloads/api/values.yaml: models {sorted((av.get('models') or {}).keys())} != usecase.yaml {models}"
                )
        for vf in (pv.get("promote") or {}).get("valuesFiles") or []:
            if not vf.startswith(f"use-cases/{uc}/"):
                error(
                    f"{r}/workloads/pipelines/values.yaml: promote.valuesFiles {vf!r} outside the use case"
                )
        # 4. the chart templates are the platform's: a use case owns values, not templates
        for chart in ("api", "serving", "pipelines"):
            tdir = UC_TEMPLATE / "workloads" / chart / "templates"
            udir = charts / chart / "templates"
            if not udir.exists():
                continue
            for tf in sorted(tdir.glob("*")):
                uf = udir / tf.name
                if not uf.exists() or uf.read_text(encoding="utf-8") != tf.read_text(encoding="utf-8"):
                    error(f"{rel(uf)}: differs from the platform's {rel(tf)} (charts are the platform's; change the template, then every use case)")
        # 5. isolation: nothing under this use case names another one
        for other in ucs:
            if other == uc:
                continue
            for f in d.rglob("*"):
                if f.is_file() and not any(
                    part.startswith(".") or part.endswith(".egg-info")
                    for part in f.parts
                ):
                    try:
                        text = f.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        continue
                    if other in text:
                        error(
                            f"{rel(f)}: names use case {other!r} — use cases are isolated"
                        )
                        break


def main() -> int:
    check_chart_version()
    check_platform_repo()
    check_template_markers()

    check_kustomize_wiring(DIR_PROJECTS)
    check_kustomize_wiring(DIR_APPS)

    projects: dict[str, dict] = {}
    for path in yaml_files(DIR_PROJECTS):
        doc = load(path)
        if doc.get("kind") != "AppProject":
            error(f"{rel(path)}: expected kind AppProject, found {doc.get('kind')!r}")
            continue
        name = doc.get("metadata", {}).get("name")
        if name != path.stem:
            error(f"{rel(path)}: metadata.name {name!r} != file name {path.stem!r}")
        projects[name] = doc

    check_platform_modules(projects)
    check_use_cases()

    with_app: set[str] = set()
    for path in yaml_files(DIR_APPS):
        doc = load(path)
        r = rel(path)
        if doc.get("kind") != "Application":
            error(f"{r}: expected kind Application, found {doc.get('kind')!r}")
            continue
        name = doc.get("metadata", {}).get("name")
        if name != path.stem:
            error(f"{r}: metadata.name {name!r} != file name {path.stem!r}")

        spec = doc.get("spec", {})
        project = spec.get("project")
        with_app.add(project)
        if project == "default":
            error(f"{r}: project 'default' restricts nothing")
            continue
        if project in PLATFORM_PROJECTS:
            error(
                f"{r}: project {project!r} is the platform project; a workload must not use it"
            )
            continue
        if project != name:
            error(
                f"{r}: project {project!r} but Application is {name!r} (1 workload = 1 AppProject of the same name)"
            )
        if project not in projects:
            error(f"{r}: project {project!r} does not exist in projects/")
            continue
        pspec = projects[project].get("spec", {})

        sources = sources_of(spec)
        if not sources:
            error(f"{r}: neither `source` nor `sources`")
        allowed = pspec.get("sourceRepos", [])
        for src in sources:
            if src.get("repoURL") not in allowed:
                error(
                    f"{r}: repoURL {src.get('repoURL')!r} not in sourceRepos of projects/{project}.yaml"
                )
            if src.get("path") and not (ROOT / src["path"]).exists():
                error(f"{r}: path {src['path']!r} does not exist in the repo")
            for vf in (src.get("helm") or {}).get("valueFiles") or []:
                if src.get("path") and not (ROOT / src["path"] / vf).exists():
                    error(f"{r}: values file {vf!r} not found under {src['path']}")
        git_repos = {s.get("repoURL") for s in sources if not s.get("chart")}
        if len(git_repos) > 1:
            error(
                f"{r}: {len(git_repos)} Git repositories ({sorted(git_repos)}); 1 workload = 1 repo"
            )

        group = (doc.get("metadata", {}).get("labels") or {}).get(
            "mlops-ct-platform.dev/group"
        )
        if group != path.parent.name:
            error(
                f"{r}: label mlops-ct-platform.dev/group is {group!r} but the file lives in group {path.parent.name!r}"
            )
        archetype = (doc.get("metadata", {}).get("annotations") or {}).get(
            ARCHETYPE_ANNOTATION
        )
        if archetype is not None and archetype not in ARCHETYPES:
            error(
                f"{r}: unknown archetype {archetype!r}; known: {sorted(ARCHETYPES)} (docs/design/archetypes.md)"
            )

        dest = spec.get("destination", {})
        ns, server = dest.get("namespace"), dest.get("server")
        dests = pspec.get("destinations", [])
        if not any(
            d.get("namespace") == ns and d.get("server") == server for d in dests
        ):
            error(
                f"{r}: destination {server}/{ns} not in destinations of projects/{project}.yaml"
            )
        if any(d.get("namespace") == "*" for d in dests):
            error(
                f"projects/{project}.yaml: destinations with wildcard '*'; a workload is confined to one namespace"
            )
        if ns != name:
            error(f"{r}: destination namespace {ns!r} != workload name {name!r}")
        if server != EXPECTED_SERVER:
            error(f"{r}: destination.server {server!r}; expected {EXPECTED_SERVER!r}")

        opts = (spec.get("syncPolicy") or {}).get("syncOptions") or []
        if "CreateNamespace=true" not in opts:
            error(f"{r}: CreateNamespace=true missing in syncOptions")

        allowed_cluster = [{"group": "", "kind": "Namespace"}]
        if pspec.get("clusterResourceWhitelist") != allowed_cluster:
            error(
                f"projects/{project}.yaml: clusterResourceWhitelist must be exactly {allowed_cluster}; "
                f"found {pspec.get('clusterResourceWhitelist')}"
            )

    for name in projects:
        if name in PLATFORM_PROJECTS:
            continue
        if name not in with_app:
            error(f"projects/{name}.yaml: AppProject without Application in apps/")

    if errors:
        print(f"✗ {len(errors)} incoherence(s):\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    ucs = use_cases()
    on = [u for u in ucs if u in resources_of(DIR_APPS / "kustomization.yaml")]
    print(
        f"✓ {len(with_app)} workload(s), {len(list(DIR_PLATFORM.iterdir())) - 1} platform module(s) "
        f"and {len(ucs)} use case(s) coherent (deployed in the demo: {', '.join(on) or 'none'})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
