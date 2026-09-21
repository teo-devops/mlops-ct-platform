# Module: event-bus (Redpanda, opt-in)

| | |
|---|---|
| **Contract** | publish/subscribe of prediction records — the same JSON document the prediction log writes (`{ts, request_id, model, model_version, features…, prediction, score, source}`) — on topic `predictions`; the platform provisions topics, a use case publishes and consumes |
| **Demo implementation** | Redpanda single node (Kafka protocol, no JVM, no quorum, no operator), internal listener `redpanda.redpanda.svc.cluster.local:9093`, no TLS/SASL (NetworkPolicies decide who reaches it); Console at http://redpanda.localhost:8088; topics by a PostSync Job (`manifests/topics-job.yaml`), like MinIO's buckets |
| **Pinned version** | chart 26.2.3 (Redpanda v26.2.2, Console v3.9.0) |
| **Namespace** | redpanda |
| **Producers / consumers** | the use-case API (`api/app/event_bus.py`, on when `eventBus.enabled` in its chart) publishes every record keyed by model, next to the S3 log; `ctsteps drift --source kafka` reads its window from the topic by timestamp (`eventBus.enabled` in the pipelines chart) |
| **Enable** | uncomment `- redpanda` in `gitops/environments/demo/platform/kustomization.yaml`, commit; then `eventBus.enabled: true` in the use case's `workloads/{api,pipelines}/values-demo.yaml`, commit. Nothing out of band |
| **Disable** | comment the line and set `eventBus.enabled: false` back: the API and the monitor fall back to the S3 log, which never stopped being written |

Wave 2. What the bus changes and what it does not: the loop is the same (S3 stays the batch source of
truth and the fallback), the transport changes — latency (records are available in milliseconds, not at
the next flush) and fan-out (the drift monitor, a shadow model, a label join for concept drift, a business
dashboard can all consume the same stream without scraping objects). The API never blocks on the bus: an
outage costs `uc_event_bus_errors_total`, not availability. The monitor keeps no consumer group and commits
nothing: windows are read by timestamp (`offsets_for_times`) and overlap on purpose.

## Kafka via Strimzi: the more robust option, and the platform is open to it

Redpanda is the right size for kind — one pod, Kafka-compatible. In production a **Kafka cluster
operated by Strimzi** is the more robust choice and this platform is open to it: replication factor 3 with
rack awareness, KRaft controllers, the operator handling rolling upgrades and certificate rotation, `KafkaTopic`
/ `KafkaUser` as declarative resources under GitOps, Cruise Control for rebalancing, MirrorMaker 2 for
disaster recovery, and Kafka Streams/Connect if the label join grows beyond a batch step. None of that
changes the loop: the producer (`api/app/event_bus.py`) and the consumer (`ctsteps io_kafka`) speak the
Kafka protocol and only know a bootstrap URL and a topic name.

Replacing the module = a directory `gitops/environments/demo/platform/strimzi/` with the operator chart
(pinned, from `https://strimzi.io/charts/`) plus these manifests instead of the Redpanda values — the same
contract, honoured by other objects:

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: platform
  namespace: kafka
  annotations:
    strimzi.io/node-pools: enabled
    strimzi.io/kraft: enabled
spec:
  kafka:
    version: 4.0.0
    listeners:
      - name: internal
        port: 9093
        type: internal
        tls: false           # prod: tls: true + authentication: {type: scram-sha-512}
    config:
      default.replication.factor: 3
      min.insync.replicas: 2
      offsets.topic.replication.factor: 3
  entityOperator:
    topicOperator: {}
    userOperator: {}
---
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaNodePool
metadata:
  name: brokers
  namespace: kafka
  labels:
    strimzi.io/cluster: platform
spec:
  replicas: 3
  roles: [controller, broker]
  storage:
    type: jbod
    volumes:
      - id: 0
        type: persistent-claim
        size: 100Gi
        deleteClaim: false
---
# The topic of the contract as a declarative resource: this replaces topics-job.yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: predictions
  namespace: kafka
  labels:
    strimzi.io/cluster: platform
spec:
  partitions: 12
  replicas: 3
  config:
    retention.ms: 604800000
```

And in the use case, one value per chart: `eventBus.bootstrap: platform-kafka-bootstrap.kafka.svc.cluster.local:9093`
(`eventBus.namespace: kafka`). With SASL on, the API and the pipelines receive a `KafkaUser` secret the same way
they receive their artifact-store keys (`use-cases/<name>/scripts/secrets.sh`). On AWS the counterpart is MSK
with IAM authentication (docs/design/profiles.md).

Gaps, on purpose: no shadow-model consumer and no label feedback topic yet (they are the reason a bus exists;
the record schema is ready for them); the API produces with `acks=1` and no idempotence (a demo trade-off:
latency over exactly-once); no schema registry — the record is JSON, its schema is the prediction log's.
