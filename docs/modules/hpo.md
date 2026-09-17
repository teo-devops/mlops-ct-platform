# Module gap: hpo

| | |
|---|---|
| **Contract it would implement** | hyper-parameter search inside `train` |
| **Production counterpart** | Katib (Kubeflow), Optuna |
| **Where it plugs in** | between `preprocess` and `train`: a fan-out of `train` with different params, `evaluate` picks the best on the holdout before the champion gate |
| **What stands in for it in the demo** | `UseCase.build_model` returns a fixed estimator |

Argo Workflows can fan out natively (`withParam`), which is how a Katib-less version would start.
