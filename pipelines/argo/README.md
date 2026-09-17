# Argo Workflows adapter

Implemented per use case as a Helm chart (`use-cases/<uc>/workloads/pipelines`) so that image,
buckets, secrets and schedules are values. Generic traits:

* one `step` container template, parameterised by `step` and `extra` flags; `--run-id` is the
  Workflow name, which names the dataset folder in the artifact store;
* output parameters read from `/tmp/outputs/{result.json,mlflow_run_id,promote,version}` with
  defaults, so steps that do not produce them still succeed;
* the gate is `when: "{{tasks.evaluate.outputs.parameters.promote}} == true"` on `register` and `promote`;
* `promote` is its own template with the Git credential, reused by `ct-promote` (manual
  promotion / rollback);
* `workflowMetadata.labelsFrom` stamps `ct.mlops/model` and `ct.mlops/trigger` on every run, which
  is how the drift monitor avoids submitting a retrain while one is in flight;
* CronWorkflows use `schedules:` (Argo Workflows v4 removed `schedule:`).
