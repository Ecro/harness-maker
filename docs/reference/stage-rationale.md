# Stage rationale moved out of the rendered commands

Every byte of a rendered `/hm:` stage command is re-read on each later model call of the session
(HM-LIGHT-LANE: stage bodies are 60.5% of main-context carry). Rationale that changes nothing the
model does at run time lives here instead. Each entry names where it used to sit.

## `templates/stages/execute.md.j2`

> **Measured cost of the fan-out it replaces:** ≈330k subagent tokens and ≈2 minutes per round. > **Measured cost of collapsing it:** on the round that produced this change, all six blocking > issues were solo finds — no defect was reported by more than one lens, so the independent > contexts, not the lens text, produced that spread. The trade is recorded rather than hidden.

## `templates/stages/execute.md.j2`

Measured across two tasks: eleven Phase A.5 findings were the single sentence "this test passes before the implementation exists" — five tautologies satisfied by a model's `extra="forbid"` guard, six anchors satisfied by prose the template already shipped. Each cost a reviewer round that could have been one pytest run.

## `templates/stages/review.md.j2`

> Why: the results directory is keyed by slug and round, so re-running `/hm:review` on the same > slug lands in the **same** directory. Without the run id, a previous invocation's files > vouch for every lens in an invocation where only one returned — `blocks_approval: false`, > four dead lenses reported as exercised. Measured. The round keying separates a pass from a > round; it does not separate one invocation from the next.
