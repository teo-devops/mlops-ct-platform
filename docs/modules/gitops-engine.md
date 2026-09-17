# Module: gitops-engine

| | |
|---|---|
| **Contract** | Applications / AppProjects reconciled from Git |
| **Demo implementation** | Argo CD (chart `argo/argo-cd`) managing itself via `overlays/demo/argo-cd.yaml` + `config/argo-cd/values.yaml` |
| **Pinned version** | chart 10.2.2 (Argo CD v3.4.6) |
| **Namespace** | argocd |
| **Replace with** | Argo CD HA (prod); Flux would need a different app-of-apps layout |
| **Disable** | not applicable — it is the engine |

Installed once by `scripts/20-install.sh` (four phases: credential, chart, wait for CRDs, root-app); from then on it upgrades itself from the same values file. Two additions over the inherited values: a Lua health check for `Application` resources so that sync-waves between modules actually order them, and declarative Helm repositories (OCI for KServe). Dex is off; RBAC is ready for it.
