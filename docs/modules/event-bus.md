# Module: event-bus (Redpanda or Strimzi, opt-in)

| | |
|---|---|
| **Contract** | publish/subscribe of prediction records — the same JSON document the prediction log writes (`{ts, request_id, model, model_version, features…, prediction, score, source}`) — on topic `predictions`; the platform provisions topics, a use case publishes and consumes |
| **Demo implementation** | Redpanda single node (Kafka protocol, no JVM, no quorum, no operator), internal listener `redpanda.redpanda.svc.cluster.local:9093`, no TLS/SASL (NetworkPolicies decide who reaches it); Console at http://redpanda.localhost:8088; topics by a PostSync Job (`manifests/topics-job.yaml`), like the artifact store's buckets |
| **Pinned version** | chart 26.2.3 (Redpanda v26.2.2, Console v3.9.0) |
| **Other implementation** | Kafka via the Strimzi operator, module `strimzi` ([strimzi.md](strimzi.md)): bootstrap `platform-kafka-bootstrap.kafka.svc.cluster.local:9093`, namespace `kafka`, topic as a `KafkaTopic` |
| **Namespace** | redpanda |
| **Producers / consumers** | the use-case API through `ctserve.Telemetry` (libs/ctserve — the API calls `emit(model, record)`, the platform library publishes keyed by model when `CT_EVENT_BUS_BOOTSTRAP` is set, next to the S3 log; `eventBus.enabled` in the use case's api chart sets it); `ctsteps drift --source kafka` reads its window from the topic by timestamp (`eventBus.enabled` in the pipelines chart) |
| **Enable** | `make module ENABLE=redpanda COMMIT=1`; then `eventBus.enabled: true` in the use case's `workloads/{api,pipelines}/values-demo.yaml`, commit. Nothing out of band |
| **Disable** | `make module DISABLE=redpanda COMMIT=1` and set `eventBus.enabled: false` back: the API and the monitor fall back to the S3 log, which never stopped being written |
| **In the demo** | off: the example use case runs on the S3 log (decisions.md #5). Exercised on 2026-09-21: 600 drifted requests → 60+ records on the topic → `ctsteps drift --source kafka` (rows=392, PSI 0.72) → retrain → `edcc425`/`583e4d4` promoted v2 |

Wave 2. What the bus changes and what it does not: the loop is the same (S3 stays the batch source of
truth and the fallback), the transport changes — latency (records are available in milliseconds, not at
the next flush) and fan-out (the drift monitor, a shadow model, a label join for concept drift, a business
dashboard can all consume the same stream without scraping objects). The API never blocks on the bus: an
outage costs `uc_event_bus_errors_total`, not availability. The monitor keeps no consumer group and commits
nothing: windows are read by timestamp (`offsets_for_times`) and overlap on purpose.

## Kafka via Strimzi

Redpanda is the right size for kind — one pod, Kafka-compatible. Kafka operated by Strimzi is the
production-shaped option and it is implemented as its own opt-in module, [strimzi](strimzi.md):
KRaft, `KafkaNodePool`, `KafkaTopic` under GitOps, the operator handling upgrades and certificates.
None of that changes the loop: the producer (`ctserve.EventBus`) and the consumer (`ctsteps.io_kafka`)
speak the Kafka protocol and only know a bootstrap URL and a topic name — switching a use case is two
values (`eventBus.bootstrap`, `eventBus.namespace`). On AWS the counterpart is MSK with IAM
authentication (docs/design/profiles.md).

Gaps, on purpose: no shadow-model consumer and no label feedback topic yet (they are the reason a bus exists;
the record schema is ready for them); the API produces with `acks=1` and no idempotence (a demo trade-off:
latency over exactly-once); no schema registry — the record is JSON, its schema is the prediction log's.
