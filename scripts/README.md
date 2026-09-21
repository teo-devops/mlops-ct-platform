# Scripts

Grouped by purpose; the scripts of the **launch flow carry a continuous number (01 → 10)** so the
order is visible in any file listing, and the `Makefile` runs the same order (`make help`).
Steps 01–05 and 10 are the platform's; **06–09 belong to the use case** (`use-cases/<name>/scripts/`)
and `make` runs them for `USE_CASE=<name>` (default `automated-listing-engine`). The platform never names a use case.
Unnumbered scripts are on-demand tools. Every script resolves paths from the repository root
through `lib.sh` (`REPO_ROOT`), so they run from anywhere, and every one refuses to touch a
kubectl context other than `kind-ct`.

| # | Script | `make` | What it does |
|---|---|---|---|
| 01 | `cluster/01-prereqs.sh` | `prereqs` | tools, GitHub credential, WARP/TLS warning |
| 02 | `cluster/02-up.sh` | `up` | kind cluster from `cluster/kind.yaml`, image preload from `cluster/images.txt`, ingress-nginx |
| 03 | `platform/03-secrets.sh` | `secrets` | platform namespaces, artifact-store identities, platform Secrets (opt-in modules only while enabled); then every `use-cases/*/scripts/secrets.sh` |
| — | `use-cases/<uc>/scripts/secrets.sh` | (via 03) | the use case's namespaces, consumer credentials, Git credential, data-source state |
| 04 | `platform/04-install.sh` | `bootstrap` | Argo CD in four phases (credential → chart → wait → root-app); the only imperative step of the control plane |
| 05 | `platform/05-wait.sh` | `wait` | platform Applications Synced/Healthy (`SCOPE=<uc>` for a use case) |
| 06 | `use-cases/<uc>/scripts/06-build-images.sh` | `build` | steps + API images → `kind load` |
| 07 | `use-cases/<uc>/scripts/07-run-pipeline.sh` | `pipeline` | submit `ct-pipeline` for every model and wait (bootstraps the models on the first run) |
| 08 | `use-cases/<uc>/scripts/08-smoke.sh` | `smoke` | real request, fallback drill, network-policy probe |
| 09 | `use-cases/<uc>/scripts/09-induce-drift.sh` | `drift` | the closed loop: drifted world → monitor → retrain → promotion commit → new version served |
| 10 | `cluster/10-down.sh` | `down` | delete the cluster |
| — | `platform/status.sh` | `status` | Applications with owner group, every served model and pipeline, URLs and passwords |
| — | `platform/04-install.sh credential status\|add\|remove` | — | the Argo CD repository credential of a private fork |
| — | `use-cases/<uc>/scripts/promote.sh` | `promote` | promote (or roll back to) a registry version: `make promote MODEL=fraud VERSION=1` |
| — | `repo/validate-coherence.py` | `lint` | the GitOps tree is coherent (names, projects, kustomize wiring, platform modules) |
| — | `repo/register-workload.py` | — | register a workload from the templates into a group: `<name> <path> --group <shared\|use-case>` |
| — | `repo/render.sh` | `render` | what Argo CD would apply (rendered manifests) |

`make demo` = 02 → 03 → 04 → 05 → 06 → 07 → 08.
