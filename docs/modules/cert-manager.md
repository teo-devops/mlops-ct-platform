# Module: cert-manager

| | |
|---|---|
| **Contract** | X.509 certificates for webhooks |
| **Demo implementation** | jetstack/cert-manager |
| **Pinned version** | v1.21.2 |
| **Namespace** | cert-manager |
| **Replace with** | any cert-manager-compatible issuer; in prod also the TLS of the ingresses |
| **Disable** | only if serving is also disabled (KServe's webhook needs it) |

Wave 1. `startupapicheck` is off (a Helm-hook Job that flaps under Argo CD). KServe's `serving-cert` is issued by its own self-signed Issuer; the CA bundles injected into webhooks are ignored in Argo CD diffs (`gitops/argo-cd/values.yaml`).
