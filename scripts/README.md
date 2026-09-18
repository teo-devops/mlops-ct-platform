# Scripts

Grouped by purpose; the scripts of the **launch flow carry a continuous number (01 → 10)** so the
order is visible in any file listing, and the `Makefile` runs the same order (`make help`).
Unnumbered scripts are on-demand tools. Every script resolves paths from the repository root
through `lib.sh` (`REPO_ROOT`), so they run from anywhere, and every one refuses to touch a
kubectl context other than `kind-ct`.

| # | Script | `make` | What it does |
|---|---|---|---|
| 01 | `cluster/01-prereqs.sh` | `prereqs` | tools, GitHub credential, WARP/TLS warning |
| 02 | `cluster/02-up.sh` | `up` | kind cluster from `cluster/kind.yaml`, image preload from `cluster/images.txt`, ingress-nginx |
| 03 | `platform/03-secrets.sh` | `secrets` | namespaces + demo Secrets + the `ct-data-source` ConfigMap, **before** the first sync |
| 04 | `platform/04-install.sh` | `bootstrap` | Argo CD in four phases (credential → chart → wait → root-app); the only imperative step of the control plane |
| 05 | `platform/05-wait.sh` | `wait` | platform Applications Synced/Healthy |
| 06 | `demo/06-build-images.sh` | `build` | steps + API images → `kind load` |
| 07 | `demo/07-run-pipeline.sh` | `pipeline` | submit `ct-pipeline` for every model and wait (bootstraps the models on the first run) |
| 08 | `demo/08-smoke.sh` | `smoke` | real request, fallback drill, network-policy probe |
| 09 | `demo/09-induce-drift.sh` | `drift` | the closed loop: drifted world → monitor → retrain → promotion commit → new version served |
| 10 | `cluster/10-down.sh` | `down` | delete the cluster |
| — | `platform/status.sh` | `status` | Applications, models, pipelines, URLs and passwords |
| — | `platform/credentials.sh` | — | the Argo CD repository credential: `status` / `add` / `remove` / `admin` |
| — | `platform/deploy-local.sh` | `deploy-local` | same charts and values through Helm, on a cluster **without** Argo CD (dev loop) |
| — | `demo/promote.sh` | `promote` | promote (or roll back to) a registry version: `make promote MODEL=fraud VERSION=1` |
| — | `repo/validate-coherence.py` | `lint` | the GitOps tree is coherent (names, projects, kustomize wiring, platform modules) |
| — | `repo/register-workload.py` | — | register a workload from the templates into a group: `<name> <path> --group <shared\|use-case>` |
| — | `repo/render.sh` | `render` | what Argo CD would apply (rendered manifests) |

`make demo` = 02 → 03 → 04 → 05 → 06 → 07 → 08.
