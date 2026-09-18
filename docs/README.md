# Documentation

Reading order for someone new to the repository:

1. [design/architecture.md](design/architecture.md) — the four domains, the synchronous and asynchronous paths, namespaces and network
2. [design/contracts.md](design/contracts.md) — the six contracts every module honours, and the step CLI
3. [design/ct-loop.md](design/ct-loop.md) — the continuous-training loop step by step, triggers, drift policy
4. [modules/](modules/README.md) — one card per platform module, including the documented gaps
5. [decisions.md](decisions.md) — ADRs: why things are the way they are (read before "improving" anything)
6. [../use-cases/listing-engine/docs/](../use-cases/listing-engine/docs/) — the example use case: instance architecture, case study, runbook
7. [design/profiles.md](design/profiles.md) — demo (kind) · prod (bare-metal) · aws, same modules
8. [operations/runbook.md](operations/runbook.md) — day-to-day: retrain, promote, roll back, rotate, add a use case
9. [operations/what-the-demo-does-not-prove.md](operations/what-the-demo-does-not-prove.md) — read before extrapolating
10. [roadmap.md](roadmap.md) — what is next

Study guide (Spanish): [study-guide.es.md](study-guide.es.md) — CT theory applied to this repo, the flows, what to look at in each UI, exercises, and the expansion map (Kafka, Feast, Rollouts, Airflow, AWS).

Reference: [design/secrets.md](design/secrets.md) (out-of-band state), [design/archetypes.md](design/archetypes.md)
(workload archetypes under GitOps), [../scripts/README.md](../scripts/README.md) (scripts and their `make` targets),
[../pipelines/README.md](../pipelines/README.md) (orchestrator adapters), [../use-cases/README.md](../use-cases/README.md)
(how to add a use case).

```
docs/
├── README.md            this index
├── design/              how the platform is built: architecture, contracts, ct-loop, profiles, secrets, archetypes
├── modules/             one card per module (implemented and gaps)
├── operations/          runbook, limitations of the demo
├── study-guide.es.md    study guide (Spanish): theory, flows, UIs, exercises, expansion
├── decisions.md         ADRs
│                        (use-case documents live with the use case: use-cases/<name>/docs/)
└── roadmap.md
```
