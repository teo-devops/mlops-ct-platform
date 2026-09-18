# Documentation

Reading order for someone new to the repository:

1. [design/architecture.md](design/architecture.md) — the four domains, the synchronous and asynchronous paths, namespaces and network
2. [design/contracts.md](design/contracts.md) — the six contracts every module honours, and the step CLI
3. [design/ct-loop.md](design/ct-loop.md) — the continuous-training loop step by step, triggers, drift policy
4. [modules/](modules/README.md) — one card per platform module, including the documented gaps
5. [decisions.md](decisions.md) — ADRs: why things are the way they are (read before "improving" anything)
6. [case-study.md](case-study.md) — the Listing Engine case: symptoms → modules, ownership, SLOs
7. [design/profiles.md](design/profiles.md) — demo (kind) · prod (bare-metal) · aws, same modules
8. [operations/runbook.md](operations/runbook.md) — day-to-day: retrain, promote, roll back, rotate, add a use case
9. [operations/what-the-demo-does-not-prove.md](operations/what-the-demo-does-not-prove.md) — read before extrapolating
10. [roadmap.md](roadmap.md) — what is next

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
├── decisions.md         ADRs
├── case-study.md        the motivating case
└── roadmap.md
```
