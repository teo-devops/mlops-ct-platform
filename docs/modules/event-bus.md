# Module gap: event-bus

| | |
|---|---|
| **Contract it would implement** | publish/subscribe of prediction events and label feedback (`{ts, request_id, model, model_version, features…, prediction, score}`, the same record the prediction log writes) |
| **Production counterpart** | Kafka via Strimzi (bare-metal), MSK (aws); Redpanda single-node for a heavier demo |
| **Where it plugs in** | a platform module `gitops/environments/demo/platform/redpanda`; the API gains a Kafka producer next to `prediction_log.py`; `ctsteps drift` gains a consumer source; shadow deployments read the same topic |
| **What stands in for it in the demo** | JSONL objects in `s3://predictions`, windowed by the monitor |

The record schema is already fixed by the prediction log; the bus changes latency and fan-out (shadow models, label joins for concept drift), not the loop.
