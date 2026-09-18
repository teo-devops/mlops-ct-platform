# Use cases

A use case is a **plugin** of the platform: it brings its data, its models and its API; the
platform brings the pipeline, the gates, the registry, the serving, the monitoring and the
promotion. One directory per use case, always with the same shape:

```
use-cases/<name>/
├── README.md              what it predicts, how to try it, its models
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
2. `workloads/`: copy the three charts of `listing-engine/workloads/` and change names, image,
   models and buckets in their `values*.yaml`.
3. Register the workloads into their own group:
   `python3 scripts/repo/register-workload.py <name>-serving use-cases/<name>/workloads/serving --group <name>` (×3).
4. Give the pipelines namespace its RBAC: add it to `controller.workflowNamespaces` in
   `gitops/environments/demo/platform/argo-workflows/values.yaml` and to its `manifests/namespaces.yaml`.
5. Create its Secrets and its data-source ConfigMap before the first sync
   (`scripts/platform/03-secrets.sh` is the place to extend).
6. Build (`scripts/demo/06-build-images.sh`), commit, push. The first pipeline run promotes v1.

Nothing in the platform needs to know the use case's name beyond steps 3 and 4.

| Use case | What | Status |
|---|---|---|
| [listing-engine](listing-engine/README.md) | categorise a marketplace listing and flag fraud | runs the demo |
