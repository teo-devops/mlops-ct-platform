# Module gap: data-versioning

| | |
|---|---|
| **Contract it would implement** | every registered model version points at an immutable, addressable snapshot of the data that trained it; a past dataset can be read back by that address, and branched without copying |
| **Production counterpart** | lakeFS in front of the artifact store; Iceberg/Delta time travel where a lakehouse already exists |
| **Where it plugs in** | `ingest` reads from, and the steps write to, a lakeFS commit instead of `s3://<datasets>/<use-case>/<model>/<run_id>/`; the commit id replaces `data_hash` as the registry tag. lakeFS speaks S3, so the steps only change their endpoint and prefix |
| **What stands in for it in the demo** | one immutable prefix per run (`raw`, `train`, `holdout`, `reference` parquet) plus a content hash (`data_hash`, `ctsteps/steps/common.py`) tagged on the MLflow run and the registered version, next to `git_commit` and `reference_uri` |

The stand-in already gives lineage (model version → exact data → code → drift reference) and
reproducibility. What it lacks is a name for "the data as of Tuesday" independent of a run, and
branches to experiment on data without copying it. Worth it when several teams read the same
datasets or the data is real and mutable; the cheap first step is `mlflow.log_input` with the
dataset's digest and source, which makes the existing lineage visible in the MLflow UI.
