# Module gap: data-quality

| | |
|---|---|
| **Contract it would implement** | the `validate` gate: schema, ranges, nulls, distributions, custom expectations |
| **Production counterpart** | Great Expectations (or Pandera) with a versioned expectation suite owned by Data Engineering |
| **Where it plugs in** | `ctsteps/steps/validate.py` — replace `check_frame` with a GE checkpoint; the gate semantics (fail the run) stay |
| **What stands in for it in the demo** | declarative `ColumnCheck`s from `UseCase.schema()` |

Kept dependency-free on purpose; the step is the contract, the checker is the implementation.
