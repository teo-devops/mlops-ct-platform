# prod profile (bare-metal) — illustrative

Not reconciled by any Application. It exists to show that the production environment is the same
tree with other values: copy `overlays/demo`, rename to `overlays/prod`, point `bootstrap/root-app.yaml`
at it, and replace each module's `values.yaml` with its production values (HA engine, Istio/Gateway
for KServe, managed Postgres for MLflow, Alertmanager routes, Cilium NetworkPolicies).

Workload charts already carry a `values-prod.yaml` with the profile-specific knobs
(`workloads/*/values-prod.yaml`, `use-cases/*/workloads/*/values-prod.yaml`); the Application
templates only swap `valueFiles`. See docs/profiles.md.
