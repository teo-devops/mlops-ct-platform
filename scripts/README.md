# Scripts

Grouped by purpose, no numbers: the **Makefile is the ordered entry point** (`make help`). Every
script resolves paths from the repository root through `lib.sh` (`REPO_ROOT`), so they run from
anywhere; all of them refuse to touch a kubectl context other than `kind-ct`.

| Folder | Script | `make` target | What it does |
|---|---|---|---|
| `cluster/` | `prereqs.sh` | `prereqs` | tools, GitHub credential, WARP/TLS warning |
| | `up.sh` | `up` | kind cluster from `cluster/kind.yaml`, image preload from `cluster/images.txt`, ingress-nginx |
| | `down.sh` | `down` | delete the cluster |
| `platform/` | `secrets.sh` | `secrets` | namespaces + demo Secrets + the `ct-data-source` ConfigMap, **before** the first sync |
| | `install.sh` | `bootstrap` | Argo CD in four phases (credential → chart → wait → root-app); the only imperative step of the control plane |
| | `wait.sh` | `wait` | platform Applications Synced/Healthy |
| | `status.sh` | `status` | Applications, models, pipelines, URLs and passwords |
| | `credentials.sh` | — | the Argo CD repository credential: `status` / `add` / `remove` / `admin` |
| | `deploy-local.sh` | `deploy-local` | same charts and values through Helm, on a cluster **without** Argo CD (dev loop) |
| `demo/` | `build-images.sh` | `build` | steps + API images → `kind load` |
| | `run-pipeline.sh` | `pipeline` | submit `ct-pipeline` for every model and wait |
| | `promote.sh` | `promote` | promote (or roll back to) a registry version: `make promote MODEL=fraud VERSION=1` |
| | `smoke.sh` | `smoke` | real request, fallback drill, network-policy probe |
| | `induce-drift.sh` | `drift` | the closed loop: drifted world → monitor → retrain → promotion commit → new version served |
| `repo/` | `validate-coherence.py` | `lint` | the GitOps tree is coherent (names, projects, kustomize wiring, platform modules) |
| | `register-workload.py` | — | register a workload from the templates into a group: `<name> <path> --group <shared|use-case>` |
| | `render.sh` | `render` | what Argo CD would apply (rendered manifests) |

Execution order of the demo: `prereqs → up → secrets → bootstrap → wait → build → pipeline → smoke → drift`.
