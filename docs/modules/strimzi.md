# Module: strimzi (Kafka, opt-in)

| | |
|---|---|
| **Contract** | event-bus ([event-bus.md](event-bus.md)): the prediction records on topic `predictions`, published by the use-case APIs, read by the drift monitor; the platform provisions topics |
| **Demo implementation** | the Strimzi Cluster Operator (upstream chart) plus, from this repository, a `Kafka` cluster `platform` in KRaft mode with one `KafkaNodePool` (`dual`: one node, controller and broker), a `KafkaTopic` `predictions` (3 partitions, replication 1, 7 days) and a `PodMonitor`. Internal listener `platform-kafka-bootstrap.kafka.svc.cluster.local:9093`, no TLS/SASL (NetworkPolicies decide who reaches it) |
| **Pinned version** | chart 1.2.0 (Strimzi 1.2.0, Kafka 4.3.1, API `kafka.strimzi.io/v1`) |
| **Namespace** | kafka |
| **Metrics** | Strimzi Metrics Reporter (`metricsConfig.type: strimziMetricsReporter`, port `tcp-prometheus`), scraped by `manifests/podmonitor.yaml` — no JMX exporter configuration to maintain. The chart's Grafana dashboards expect JMX exporter names: off |
| **Enable** | `make module ENABLE=strimzi COMMIT=1`; wait for `strimzi` Healthy (the `Kafka` health check is Argo CD's own: Healthy = Ready); then in the use case's `workloads/{api,pipelines}/values-demo.yaml`: `eventBus: {enabled: true, bootstrap: platform-kafka-bootstrap.kafka.svc.cluster.local:9093, namespace: kafka}`, commit |
| **Disable** | set `eventBus.enabled: false` (or point it back at redpanda) first, commit; then `make module DISABLE=strimzi COMMIT=1`. The S3 prediction log never stopped being written |
| **Resources** | operator 384–512 Mi, broker 1 Gi (heap 512 Mi), topic operator ≤ 384 Mi, 5 Gi PVC |

**Strimzi or redpanda.** Both honour the same contract; a use case changes two values
(`bootstrap`, `namespace`) and nothing else — the producer (`ctserve.EventBus`) and the consumer
(`ctsteps.io_kafka`) are librdkafka clients that only know a bootstrap URL and a topic. Redpanda is
one pod and no operator: the lightest bus for kind. Strimzi is what production looks like on
Kubernetes: topics (and, with authentication, users) are declarative resources under GitOps instead
of a PostSync Job, the operator rolls upgrades and certificates, and the objects that grow the
cluster are the same ones the demo uses — `KafkaNodePool` replicas, replication factors, rack
awareness, Cruise Control, MirrorMaker 2. Enable one of the two, not both, for a given use case.

**From the demo to production**, same objects:

* node pools: 3 `controller` + 3 `broker` (or more), `persistent-claim` with `deleteClaim: false`;
* `default.replication.factor: 3`, `min.insync.replicas: 2`, topic `replicas: 3`, `rack.topologyKey`;
* listener `tls: true` + `authentication: {type: scram-sha-512}`, `entityOperator.userOperator`, one
  `KafkaUser` per use case with ACLs on `predictions`; its Secret reaches the use case's namespaces
  the way its artifact-store keys do (`use-cases/<name>/scripts/secrets.sh`), and the clients get
  `security.protocol`/`sasl.*` — the only code change on the path;
* `listeners[].networkPolicyPeers` to restrict the brokers from their side too;
* on AWS the counterpart is MSK with IAM authentication (docs/design/profiles.md).

Deliberately missing: a schema registry (the record is JSON, its schema is the prediction log's),
idempotent producer (`acks=1`, latency over exactly-once), Kafka UI (Redpanda Console works against
any Kafka if needed), Cruise Control (one node, nothing to rebalance).
