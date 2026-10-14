# Stage rationale moved out of the rendered commands

Every byte of a rendered `/hm:` stage command is re-read on each later model call of the session
(HM-LIGHT-LANE: stage bodies are 60.5% of main-context carry). Rationale that changes nothing the
model does at run time lives here instead. Each entry names the stage and step it used to sit in.

## `execute` Phase A.5 — why one test-reviewer dispatch

> **Measured cost of the fan-out it replaces:** ≈330k subagent tokens and ≈2 minutes per round.
> **Measured cost of collapsing it:** on the round that produced this change, all six blocking
> issues were solo finds — no defect was reported by more than one lens, so the independent
> contexts, not the lens text, produced that spread. The trade is recorded rather than hidden.

## `execute` Phase A.4 — what the false-RED screen measured

Measured across two tasks: eleven Phase A.5 findings were the single sentence "this test passes before the implementation exists" — five tautologies satisfied by a model's `extra="forbid"` guard, six anchors satisfied by prose the template already shipped. Each cost a reviewer round that could have been one pytest run.

## `review` Step 3 — why result files carry the run id

> Why: the results directory is keyed by slug and round, so re-running `/hm:review` on the same
> slug lands in the **same** directory. Without the run id, a previous invocation's files
> vouch for every lens in an invocation where only one returned — `blocks_approval: false`,
> four dead lenses reported as exercised. Measured. The round keying separates a pass from a
> round; it does not separate one invocation from the next.

## `review` Step 3.4 — why the payload is labelled `merged`

**True per-reviewer payloads need a per-reviewer source**, which exists only at Pass 1 / Pass 2 — before the merge. Persisting them is a **known gap**: capturing each reviewer's raw reply to its own file is a change to the dispatch steps above, not to this one. Until that lands, the corpus holds one honest merged payload per round rather than N dishonest per-reviewer ones. Replay of the consensus stage is possible; replay of the reviewer stage is not yet.

## `review` Step 3.4 — why persist the payload at all

**This buys nothing today and everything afterwards.** The detection check for pipeline changes has failed twice, the second time because no per-reviewer finding payload has ever been persisted anywhere in this repo — REVIEW documents are post-consensus narrative and `review-*.jsonl` holds only counts, so there was no artifact to replay against. Every round that skips this line is a round no future pipeline change can be tested on. It writes to the **base** root, so it survives `task-land`.

## `review` Step 4d — why one `finalize` call

This was three chained verbs that rewrote the findings file so each could see the last one's column. That chaining was the defect generator: `tag --file <any JSON object>` silently destroyed that file, the envelope was dropped on write-back, the write had no containment check, `record` went green on a blind retry, and the order dependence could only be expressed as prose naming one path three times. A function that reads once and returns a value has none of those. The rules are unchanged — same tag table, same disposition column, same grade.

## `review` Auto-Fix Loop — why the CLI computes the coverage union

Round 2 of this change's own review rejected the earlier wording, which told you to take the union yourself: the Grade Gate branches on the CLI's `blocks_approval` field, and this stage separately forbids substituting your own judgement for it — so a prose union asked you to override a field you may not override. With a single `--round`, a round that re-dispatched one lens reported the other four missing and the review could never be approved.
