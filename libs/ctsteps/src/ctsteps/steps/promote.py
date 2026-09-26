"""promote — make a version the champion, declaratively.

Two writes, in this order:
  1. registry: alias `champion` -> version (the old champion becomes `previous`).
  2. Git: bump `models.<model>.version` in the values file(s) and push
     (CT_PROMOTE_VALUES_FILE, comma-separated: typically the serving chart
     and the API chart, so predictor and lineage change in one commit).

The second write is the deployment. Nothing talks to the cluster: Argo CD
sees the commit, the serving layer rolls the new version with readiness
checks, and the commit itself is the audit trail. Rollback = revert it.

`CT_PROMOTE_MODE=pr` opens a pull request instead of pushing to the branch
(needs `gh` in the image); the demo pushes directly.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from mlflow import MlflowClient

from ctsteps import registry, result
from ctsteps.steps.common import Context


def bump_version(text: str, model: str, version: int) -> str:
    """Replace `version:` inside the `models.<model>:` block, keeping comments."""
    pattern = re.compile(
        rf"(^[ \t]+{re.escape(model)}:\n(?:[ \t]+(?!\S).*\n)*?[ \t]+version:[ \t]*)\"?\d+\"?",
        re.MULTILINE,
    )
    new, n = pattern.subn(rf'\g<1>"{version}"', text, count=1)
    if n != 1:
        raise SystemExit(f"could not find models.{model}.version in the values file")
    return new


def git(*args: str, cwd: Path, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True, **kw)


def push_bump(ctx: Context, version: int, trigger: str) -> str:
    s = ctx.settings
    if not (s.git_repo and s.git_token and s.values_file):
        raise SystemExit("promote needs GIT_REPO, GIT_TOKEN and CT_PROMOTE_VALUES_FILE")
    auth_repo = s.git_repo.replace(
        "https://", f"https://{s.git_user or 'x-access-token'}:{s.git_token}@"
    )
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        git("clone", "--depth", "1", "--branch", s.git_branch, auth_repo, str(repo), cwd=Path(tmp))
        git("config", "user.name", os.environ.get("GIT_AUTHOR_NAME", "ct-pipeline"), cwd=repo)
        git(
            "config",
            "user.email",
            os.environ.get("GIT_AUTHOR_EMAIL", "ct-pipeline@mlops-ct-platform.local"),
            cwd=repo,
        )
        files = [repo / f.strip() for f in s.values_file.split(",") if f.strip()]
        msg = (
            f"ct: promote {ctx.use_case.name}/{ctx.spec.name} v{version} (trigger={trigger})\n\n"
            f"pipeline-run: {ctx.run_id}\nregistry: {registry.registered_name(ctx.use_case.name, ctx.spec.name)} v{version}\n"
            f"serving-uri: {ctx.serving_uri(version)}\n\nCo-Authored-By: ct-pipeline <ct-pipeline@mlops-ct-platform.local>"
        )
        for attempt in range(5):
            for values in files:
                values.write_text(bump_version(values.read_text(), ctx.spec.name, version))
            git("add", *[str(f.relative_to(repo)) for f in files], cwd=repo)
            # Git already deploys this version (a rebuilt cluster whose registry
            # numbers from v1 again, a re-run): the deployment state matches, done.
            if (
                subprocess.run(
                    ["git", "diff", "--cached", "--quiet"], cwd=repo, check=False
                ).returncode
                == 0
            ):
                print(f"values already at v{version}: nothing to commit")
                return git("rev-parse", "HEAD", cwd=repo).stdout.strip()
            git("commit", "-m", msg, cwd=repo)
            try:
                git("push", "origin", f"HEAD:{s.git_branch}", cwd=repo)
                return git("rev-parse", "HEAD", cwd=repo).stdout.strip()
            except subprocess.CalledProcessError as e:
                # Someone pushed meanwhile (another model's promote, a human):
                # rebase onto the new tip and try again.
                print(f"push rejected (attempt {attempt + 1}): {e.stderr.strip()[-200:]}")
                git("reset", "--hard", f"origin/{s.git_branch}", cwd=repo)
                git("pull", "--rebase", "origin", s.git_branch, cwd=repo)
                time.sleep(2 + attempt * 3)
        raise SystemExit("could not push the promotion after 5 attempts")


def run(ctx: Context, *, version: int, trigger: str, dry_run: bool = False) -> dict:
    registry.setup(ctx.settings.mlflow_tracking_uri, ctx.use_case.name, ctx.spec.name)
    client = MlflowClient()
    name = registry.registered_name(ctx.use_case.name, ctx.spec.name)
    old = registry.champion_version(client, name)
    if old is not None and int(old.version) != version:
        client.set_registered_model_alias(name, "previous", old.version)
    client.set_registered_model_alias(name, registry.CHAMPION, str(version))
    commit = "dry-run" if dry_run else push_bump(ctx, version, trigger)
    return result.write(
        ctx.settings.outputs_dir,
        version=version,
        previous_version=int(old.version) if old else None,
        commit=commit,
        values_file=ctx.settings.values_file,
    )
