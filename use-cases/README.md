# Use cases

A use case is a **plugin** of the platform: it brings its data, its models and its API; the
platform brings the pipeline, the gates, the registry, the serving, the monitoring and the
promotion. One directory per use case, always with the same shape:

```
use-cases/<name>/
├── README.md              what it predicts, how to try it, its models
├── docs/                  architecture of the instance, case study, runbook — use-case docs live HERE, not in docs/
├── scripts/               secrets.sh (out-of-band state) + the flow: 06-build-images, 07-run-pipeline, 08-smoke,
│                          09-induce-drift, promote — `make` runs them with USE_CASE=<name>
├── plugin/                python package implementing ctsteps.contracts.UseCase
│   ├── src/<package>/     usecase.py (ModelSpecs, ingest, schema, build_model, evaluate), data.py …
│   ├── tests/
│   └── Dockerfile         FROM ctsteps-base: this is the image every pipeline step runs
├── api/                   the serving-side application (optional: a use case may only expose models)
└── workloads/             one Helm chart per workload, each registered as its own AppProject/Application
    ├── api/
    ├── serving/           InferenceServices — `models.<model>.version` is what promotion bumps
    └── pipelines/         WorkflowTemplates + CronWorkflows parameterised with the plugin image
```

## Adding a use case (the paved road)

1. `plugin/`: implement `UseCase` (only scikit-learn built-ins in the estimators), add tests, a
   `Dockerfile` `FROM ctsteps-base:<version>`.
2. `workloads/`: copy the three charts of `automated-listing-engine/workloads/` and change names, image,
   models and buckets in their `values*.yaml`.
3. Register the workloads into their own group:
   `python3 scripts/repo/register-workload.py <name>-serving use-cases/<name>/workloads/serving --group <name>` (×3).
4. Give the pipelines namespace its RBAC: add it to `controller.workflowNamespaces` in
   `gitops/environments/demo/platform/argo-workflows/values.yaml` and to its `manifests/namespaces.yaml`.
5. Declare its artifact-store users in `workloads/minio/values.yaml` (`users:`) and its namespaces in
   `networkPolicy.apiClients`; write `scripts/secrets.sh` delivering those keys into its namespaces
   (`minio_user_secret` from `scripts/lib.sh`) — `scripts/platform/03-secrets.sh` runs it automatically.
6. Write its flow scripts (`scripts/06-…09-…`, `promote.sh`) — copy the Automated Listing Engine ones and change
   names — then `USE_CASE=<name> make build pipeline smoke`.

The platform never names a use case: steps 3–5 are the only places it appears, all of them data.

| Use case | What | Status |
|---|---|---|
| [automated-listing-engine](automated-listing-engine/README.md) | categorise a marketplace listing and flag fraud | runs the demo |
