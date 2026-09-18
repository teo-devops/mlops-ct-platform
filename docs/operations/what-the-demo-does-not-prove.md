# What the demo does not prove

The kind profile validates the **control flow** of the platform for near-zero cost. Do not read
more into it than that.

* **High availability** — one control plane, single replicas of Argo CD, MLflow (sqlite), MinIO,
  Prometheus. Production needs replicated etcd, HA engine, managed Postgres, erasure-coded MinIO or S3.
* **Real multi-tenancy** — AppProjects isolate at deploy time and NetworkPolicies at runtime, but
  there are no ResourceQuotas, no LimitRanges, and Argo CD's own RBAC is not exercised (no SSO).
* **Autoscaling under load** — `autoscalerClass: external` (no metrics-server); the prod values
  show HPA/KServe autoscaling but nobody has load-tested them here.
* **Progressive delivery** — promotion is a rolling update with readiness; canary traffic splitting
  needs a gateway (module gap: progressive-delivery).
* **Backups** — nothing is backed up; the artifact store and the registry live on local-path volumes.
* **Data at scale** — the pipeline trains on 6 000 synthetic rows; the same steps on millions of
  rows need the resources of the prod profile and, realistically, a feature store.
* **Security hardening** — plain HTTP everywhere, demo passwords readable by anyone with `kubectl`,
  Argo Workflows server without auth. Fine for a laptop, nowhere else.
* **Ground truth** — the drift monitor works on input and prediction distributions because labels
  arrive late in the real world; concept drift (accuracy decay) needs the label feedback loop that
  the event-bus module would carry.
