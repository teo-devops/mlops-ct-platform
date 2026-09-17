"""ctsteps — continuous-training steps as containers.

Every step is a CLI subcommand (`ctsteps <step>`) with the same contract:
inputs from flags/environment, artefacts in the artifact store (S3 URIs),
metadata in the model registry (MLflow), and a small JSON result written to
`$CT_OUTPUTS_DIR/result.json` for the orchestrator to pass along.

The orchestrator (Argo Workflows, Airflow, Kubeflow Pipelines...) is an
adapter around these commands; the use case is a plugin implementing
`ctsteps.contracts.UseCase`.
"""

__version__ = "0.1.0"
