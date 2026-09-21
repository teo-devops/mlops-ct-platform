# Module: airflow (orchestration, opt-in)

| | |
|---|---|
| **Contract** | orchestration — run `ctsteps <step>` containers in order; schedules; on-demand submission. An *alternative* to [orchestration](orchestration.md) (Argo Workflows), exercised, off by default |
| **Demo implementation** | Apache Airflow on `LocalExecutor`; one `KubernetesPodOperator` per step in the use case's pipelines namespace; the DAGs of `pipelines/adapters/airflow/` delivered by git-sync from this repository; own Postgres (`manifests/postgres.yaml`); no login (SimpleAuthManager, everyone admin — like the Argo Workflows UI) |
| **Pinned version** | chart 1.22.0 (Airflow 3.2.2), `postgres:16.10-alpine`, git-sync v4.4.2 |
| **Namespace** | airflow (api-server, scheduler, dag-processor, postgres); step pods in each use case's pipelines namespace |
| **Enable** | uncomment `- airflow` in `gitops/environments/demo/platform/kustomization.yaml`, `make secrets` (creates its out-of-band state), commit. UI: http://airflow.localhost:8088 |
| **Disable** | comment the line again: Argo CD prunes the module (the Postgres PVC is `Prune=false`) |

Wave 2. Exercised on 2026-09-21 (`ct_pipeline_categorizer`: gate refused an equal challenger, then promoted v3 in commit `5b67091`). What is *exercised*: `ct_pipeline_categorizer` / `ct_pipeline_fraud` run the seven steps with the
same image, environment, arguments and resources as the Argo `WorkflowTemplate ct-pipeline`; XCom carries the
three scalars (`mlflow_run_id`, `promote`, `version`) from `result.json`; a `ShortCircuitOperator` is the gate;
`promote` pushes the deployment commit exactly as the Argo path does. Trigger a run:

```bash
curl -s -X POST http://airflow.localhost:8088/api/v2/dags/ct_pipeline_categorizer/dagRuns \
  -H 'content-type: application/json' -d '{"logical_date": null, "conf": {"trigger": "manual"}}'
```

Design notes. The platform owns the RBAC of the pipelines namespaces (`manifests/rbac.yaml`, one
Role/RoleBinding per namespace for the `airflow-scheduler` ServiceAccount) exactly as argo-workflows owns
`controller.workflowNamespaces`; a use case never writes Role/RoleBinding. The chart's Postgres subchart points
at frozen `bitnamilegacy` images (the MLflow problem, decisions.md #6), hence the 60-line Postgres of the module.
Every key the chart would otherwise regenerate on each render (fernet, API secret key, JWT) is a Secret created
by `scripts/platform/03-secrets.sh` — otherwise the Application never reaches Synced.

Gaps, on purpose: the drift monitor (`ctsteps drift`) submits **Argo** Workflows (`CT_WORKFLOW_TEMPLATE`); an
Airflow REST trigger from the monitor is the missing piece if Airflow were to replace Argo rather than sit next
to it. `make pipeline`/`make status` look at Argo Workflows only. Task logs are not persisted (LocalExecutor,
no shared volume): read them with `kubectl -n <uc>-pipelines logs`. Airflow adds ~1.5 GB and four Deployments
to the demo, which is why it stays opt-in (decisions.md #13).
