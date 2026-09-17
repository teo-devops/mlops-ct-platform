# Module: gateway-api-crds

| | |
|---|---|
| **Contract** | Gateway API types |
| **Demo implementation** | CRDs from `kubernetes-sigs/gateway-api` `config/crd/standard` |
| **Pinned version** | v1.5.1 |
| **Namespace** | gateway-system |
| **Replace with** | a Gateway implementation (Envoy Gateway, Istio, Cilium) in the prod profile |
| **Disable** | remove the line — KServe v0.20 registers the types but tolerates their absence with ingress creation disabled |

A safety net at zero cost: the same CRDs the prod profile's gateway needs.
