# Module: ingress

| | |
|---|---|
| **Contract** | HTTP entry point `*.localhost:8088` |
| **Demo implementation** | ingress-nginx installed by `scripts/cluster/up.sh` (kind provider manifest), not by Argo CD |
| **Pinned version** | controller-v1.12.1 |
| **Namespace** | ingress-nginx |
| **Replace with** | MetalLB + ingress-nginx or a Gateway API implementation (prod), ALB (aws) |
| **Disable** | everything still works in-cluster; UIs need port-forwards |

Deliberately outside GitOps: it is the piece that gives the engine its own UI, and the lab pattern (Argo-cd-Labs) keeps it imperative.
