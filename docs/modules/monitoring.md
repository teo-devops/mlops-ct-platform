# Module: monitoring

| | |
|---|---|
| **Contract** | Prometheus scrapes any ServiceMonitor/PodMonitor/PrometheusRule; batch jobs push to the Pushgateway; Grafana loads labelled ConfigMaps |
| **Demo implementation** | kube-prometheus-stack (Prometheus, Grafana, operator, kube-state-metrics, node-exporter) + prometheus-pushgateway |
| **Pinned version** | 91.4.1 / 3.8.0 |
| **Namespace** | observability |
| **Replace with** | Amazon Managed Prometheus/Grafana (aws), VictoriaMetrics — the contract is the operator CRDs and the push endpoint |
| **Disable** | remove both lines; rules and dashboards in `workloads/observability` become inert |

Wave 2. Alertmanager is off (rules fire, nobody pages), control-plane scrapes kind does not expose are off. `*SelectorNilUsesHelmValues: false` so every namespace's monitors are picked up. The CT Loop dashboard and the CT rules are a workload (`workloads/observability`), not part of this module: what to watch belongs to the platform team, the stack does not.
