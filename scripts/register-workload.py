#!/usr/bin/env python3
"""Registers a workload from the templates: two files and two kustomization lines.

    Usage:  python3 scripts/register-workload.py <name> <path> [options]

      name          workload name = AppProject = Application = namespace
      path          directory in this repository with its manifests
                    (a Helm chart with values.yaml + values-demo.yaml, or plain YAML)

    Options:
      --archetype    stateless | batch | stateful | pipeline   (default: stateless)
      --description  one line for the AppProject
      --group        identity-provider group that operates it
      --dry-run      print to stdout instead of writing files

What it does:
  1. templates/workload-appproject.yaml  -> overlays/demo/projects/<name>.yaml
  2. templates/workload-application.yaml -> overlays/demo/apps/<name>.yaml
  3. adds each file to its kustomization.yaml
  4. runs validate-coherence.py

What it does NOT do, on purpose: it never talks to the cluster or the forge.
The AppProject it writes defines privilege limits — READ IT before committing.

Inherited from teo-devops/Argo-cd-Labs scripts/alta-workload.py.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
DIR_PROJECTS = ROOT / "overlays" / "demo" / "projects"
DIR_APPS = ROOT / "overlays" / "demo" / "apps"
PLATFORM_REPO = "https://github.com/teo-devops/mlops-ct-platform.git"
ARCHETYPES = ("stateless", "batch", "stateful", "pipeline")
RX_NAME = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
RX_SEPARATOR = re.compile(r"^# =+$")


def render(template: pathlib.Path, values: dict[str, str]) -> str:
    lines = template.read_text(encoding="utf-8").splitlines(keepends=True)
    seps = [i for i, l in enumerate(lines) if RX_SEPARATOR.match(l.rstrip())]
    if len(seps) >= 2:
        lines = lines[seps[1] + 1:]
    text = "".join(lines)
    # Longest markers first so that PATH does not eat REPO_URL etc.
    for marker in sorted(values, key=len, reverse=True):
        text = text.replace(marker, values[marker])
    return text


def add_to_kustomization(kustomization: pathlib.Path, entry: str) -> bool:
    lines = kustomization.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("resources:")
    except ValueError:
        sys.exit(f"{kustomization}: no `resources:` block")
    end = start + 1
    while end < len(lines) and lines[end].startswith("  - "):
        end += 1
    entries = [l[4:].strip() for l in lines[start + 1:end]]
    if entry in entries:
        return False
    entries.append(entry)
    entries.sort(key=lambda e: (e != "platform.yaml", e))
    lines[start + 1:end] = [f"  - {e}" for e in entries]
    kustomization.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="Register a workload from the templates.")
    p.add_argument("name")
    p.add_argument("path")
    p.add_argument("--archetype", choices=ARCHETYPES, default="stateless")
    p.add_argument("--description", default=None)
    p.add_argument("--group", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    name = args.name
    if not RX_NAME.match(name):
        sys.exit(f"invalid name {name!r}: must be a valid namespace name (RFC 1123)")
    if not (ROOT / args.path).is_dir() and not args.dry_run:
        sys.exit(f"path {args.path!r} does not exist in the repository; create the chart first")

    dst_project = DIR_PROJECTS / f"{name}.yaml"
    dst_app = DIR_APPS / f"{name}.yaml"
    for d in (dst_project, dst_app):
        if d.exists() and not args.dry_run:
            sys.exit(f"{d.relative_to(ROOT)} already exists")

    values = {
        "NAME": name,
        "REPO_URL": PLATFORM_REPO,
        "PATH": args.path,
        "ARCHETYPE": args.archetype,
        "DESCRIPTION": args.description or f"{name}, confined to its namespace of the same name.",
        "GROUP": args.group or f"teo-devops/{name}",
    }
    project = render(TEMPLATES / "workload-appproject.yaml", values)
    app = render(TEMPLATES / "workload-application.yaml", values)

    if args.dry_run:
        print(f"---\n# overlays/demo/projects/{name}.yaml\n{project}")
        print(f"---\n# overlays/demo/apps/{name}.yaml\n{app}")
        return 0

    dst_project.write_text(project, encoding="utf-8")
    dst_app.write_text(app, encoding="utf-8")
    add_to_kustomization(DIR_PROJECTS / "kustomization.yaml", f"{name}.yaml")
    add_to_kustomization(DIR_APPS / "kustomization.yaml", f"{name}.yaml")
    print(f"✓ overlays/demo/projects/{name}.yaml\n✓ overlays/demo/apps/{name}.yaml\n✓ both added to kustomization.yaml\n")

    code = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate-coherence.py")]).returncode
    print(f"""
Left to do, and not done by this script:
  1. READ overlays/demo/projects/{name}.yaml — it defines the privilege limits.
  2. If the workload needs a Secret TO START (a Job, a private image, S3
     credentials), create it BEFORE merging: scripts/15-demo-secrets.sh.
  3. Commit and push. Argo CD picks it up on the next reconciliation.
""")
    return code


if __name__ == "__main__":
    sys.exit(main())
