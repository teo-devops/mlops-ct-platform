# Module: serving

| | |
|---|---|
| **Contract** | `InferenceService` + `storageUri`; endpoint `<model>-predictor.<ns>.svc` |
| **Demo implementation** | KServe Standard mode (three charts: `kserve-crd`, `kserve-resources`, `kserve-runtime-configs`), sklearn runtime only |
| **Pinned version** | v0.20.0 |
| **Namespace** | kserve (controller), predictors in the use-case namespace |
| **Replace with** | Seldon Core, BentoML, a plain Deployment reading the same `storageUri` — the contract is the URI layout and the v1 predict protocol |
| **Disable** | remove three lines (`kserve-crd`, `kserve`, `kserve-runtimes`); the serving workload then needs another implementation |

Waves 2/3/4. No Knative, no Istio, no ingress creation (hence no model canary — see progressive-delivery.md): the API reaches predictors in-cluster. Cluster-wide S3 defaults (`kserve.storage.s3`) mean a workload's credential Secret carries only keys. `autoscalerClass: external` because kind has no metrics-server; the prod values switch to HPA. Only `kserve-sklearnserver` is enabled; the step contract pins the exact scikit-learn/numpy/joblib versions of that image so pickles load.
