---
type: research
task_slug: antigravity-second-opinion-timeout
status: complete
created: 2026-08-08
tags: [harness-maker, research, second-opinion, antigravity, agy, observability]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[PLAN-second-opinion-multi-model]]", "[[PLAN-second-opinion-invocation-and-slug-cap]]", "[[wiki:architecture second-opinion-invoker]]", "[[fail:tooling agy-print-flag-swallows-next-flag]]"]
summary: "Timeouts are model-tier latency (Gemini 3.1 Pro High) exceeding the 240s cap, not subscription quota"
---

# RESEARCH — antigravity second-opinion timeouts

## 🎯 Recommended Direction

**The timeouts are not quota exhaustion. They are the configured model tier —
`Gemini 3.1 Pro (High)` — exceeding agy's native `--print-timeout 240s` on
real-sized review/plan prompts.** Reproduced here with a controlled A/B on an
identical 41 038-byte prompt:

| Model | Elapsed | Outcome |
|---|---|---|
| `Gemini 3.1 Pro (High)` | **4m04s** | exit 1, `Error: timeout waiting for response`, empty stdout |
| `Gemini 3.6 Flash (Medium)` | **14s** | exit 0, valid JSON, one `critical` + further findings |

The recommended direction is to **change the antigravity model tier** (the
default in `models.py:467` and `second_opinion_invoke.py:28`), not to raise the
timeout. Raising the cap trades a skip for a 4–5 minute stall in every
`/hm:review` and `/hm:plan`; the Flash tier returns a substantive, schema-shaped
payload in 14s. A secondary, independent defect (below) accounts for the other
half of antigravity's loss: `agy` ships a `--json-schema` flag that the invoker
does not use, so 9 of 20 losses are parse failures rather than timeouts.

**Quota is separately and correctly labelled.** When the subscription is
exhausted, `agy` says so and the ledger records it verbatim — `subscription quota
reached (resets ~18h)`. That string appears exactly **twice**, both on
2026-07-15, and never in any timeout row. So the answer to "is it token
exhaustion?" is: no, and the harness would have told you if it were.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary — the
failure is in an invocation contract with an external CLI) and **Risk /
observability** (secondary — the question "how would I know?" is a telemetry
question). `--deep` was not set; no Phase 0 interview ran.

## 📊 Evidence — ledger measurement

`.claude/observability/second-opinion.jsonl`, 112 rows. Per CLAUDE.md's
aggregation contract: call rows only (`finding_ref == "n/a"`), `stage: health`
excluded, `(skipped + failed) / total` **per model**.

| Model | Calls | Lost | Loss rate |
|---|---|---|---|
| codex | 48 | 1 | **2.1 %** |
| antigravity | 51 | 20 | **39.2 %** |
| — antigravity `review` | 29 | 12 | 41.4 % |
| — antigravity `plan` | 22 | 8 | 36.4 % |

Antigravity's 20 losses decompose into three distinct causes:

| Cause | Count | `skip_reason` signature | Status recorded |
|---|---|---|---|
| **Native print-timeout** | **8** | `exit 1: Error: timeout waiting for response` | `skipped` |
| **Payload parse failure** | **9** | `payload unreadable … found 0 JSON payloads` (variants) | `failed` |
| **Subscription quota** | **2** | `subscription quota reached (resets ~17h/~18h)` | `skipped` |
| Vacuous-invocation era | 1 | `agy ignored the stdin prompt and replied to the --sandbox flag itself` | `failed` |

Timeout onset is dated. The first timeout row is **2026-07-27**; every row
before that date is a parse failure or a quota hit. That is two days after
`b80c3c2c fix(second-opinion): own both CLI invocations in a tested module`
landed — i.e. timeouts began only once the invocation was *fixed* and agy
started actually receiving the full prompt. Before that fix, per
`[fail:tooling] agy-print-flag-swallows-next-flag`, `--print` swallowed
`--sandbox` as its value and the prompt was never read, so every call was
trivially fast and vacuously "successful". **The timeouts are the visible cost
of the invocation finally working.**

Timeout distribution is stage-skewed toward `review` (7 of 8), which is the
stage carrying the largest prompt — consistent with a latency-vs-payload-size
mechanism and inconsistent with quota (quota is time-based, not size-based).

## 📐 Evidence — live probes (this session, 2026-08-08)

All probes used the invoker's exact argv shape from
`second_opinion_invoke.build_agy_argv`.

1. **Trivial prompt, `Pro (High)`, cold** — `{"findings": []}` returned in
   **117s**. A no-op prompt consumed 49 % of the 240s budget.
2. **Trivial prompt, `Pro (High)`, warm** — 15s, 19s on two repeats. So latency
   is *highly variable*, not uniformly slow; cold-start / queueing dominates.
   This variance is why the failure is intermittent ("자꾸" rather than "항상").
3. **Trivial prompt, `Flash (Medium)`** — **7.7s**.
4. **41 KB prompt, `Pro (High)`** — **4m04s → timeout, exit 1, empty stdout**.
5. **41 KB prompt, `Flash (Medium)`** — **14s, exit 0, valid JSON payload**.
6. **Flag-placement control** — `--print-timeout 10s` placed *after* the prompt
   value returned at 15s with exit 1 and the exact stderr string
   `Error: timeout waiting for response`. This confirms two things: the trailing
   flag placement in `build_agy_argv` **is** honoured (no repeat of the
   `--print` arity bug), and the 8 ledger rows are agy's native timeout, not the
   process-level `AGY_TIMEOUT_S=300` backstop — which has never fired (no
   `timeout after 300s` row exists).

`agy models` inventory (live): `gemini-3.6-flash-{high,medium,low}`,
`gemini-3.5-flash-{high,medium,low}`, `gemini-3.1-pro-{high,low}`,
`claude-sonnet-4-6`, `claude-opus-4-6-thinking`, `gpt-oss-120b-medium`.
Note the harness default names the **oldest pro tier** in the list.

## 🛠️ Approaches Found

### A. Downshift the antigravity model tier (recommended)

| Field | Content |
|---|---|
| Approach | Change `DEFAULT_ANTIGRAVITY_MODEL` / `AntigravityConfig.model` from `Gemini 3.1 Pro (High)` to a Flash tier (`Gemini 3.6 Flash (High)` or `(Medium)`) |
| Assumption | A second-opinion *voter* needs adequate recall, not frontier depth — consensus is k-of-N with K=2, so this model is one voice among several, and Codex covers the deep-reasoning slot |
| Evidence | Probe 5: identical prompt, 14s, valid JSON, surfaced a `critical` finding. Probe 4: same prompt, same tier config, total loss |
| Trade-off | Lower per-finding depth from this voter, in exchange for the voter actually existing 40 % more often. A voice that times out contributes exactly zero |
| Compatibility | Single-value config change; `model` is deliberately free-text (`models.py:459` — `agy models` has no stable machine ID), no schema migration, no render-surface change beyond the default literal |
| Risk | **low** |

Open sub-question: `Flash (High)` vs `Flash (Medium)` was not measured; only
Medium was probed. `Flash (High)` is the natural first candidate if depth
matters more than the 14s figure.

### B. Raise the timeout budget

| Field | Content |
|---|---|
| Approach | Raise `--print-timeout` past 240s and `AGY_TIMEOUT_S` past 300s |
| Assumption | The calls would succeed given more time |
| Evidence | **Unverified — and probe 4 is evidence against it.** 4m04s produced *zero* output bytes; nothing indicates the call was near completion. agy's own default `--print-timeout` is 5m0s, so the harness is already running *below* the vendor default |
| Trade-off | Every `/hm:review` and `/hm:plan` stalls 4–8 minutes on a *blocking* subprocess call, for a payload the Flash tier delivers in 14s. Directly contradicts the repo's context/time-economy work |
| Compatibility | Trivial to implement |
| Risk | **medium** — converts a loud, recorded skip into a silent multi-minute stall |

### C. Adopt `agy --json-schema` (independent, addresses the *other* 9 losses)

| Field | Content |
|---|---|
| Approach | Pass `--json-schema <path>` on the agy argv, reusing the existing `.claude/schemas/second-opinion-finding.schema.json` that Codex already uses via `--output-schema` |
| Assumption | agy's `--json-schema` enforces structured output as documented in `agy --help` |
| Evidence | `agy --help` (live, this session): *"Optional JSON schema string or path to a schema file to enforce structured output"*. **Not empirically probed** — the flag's real behaviour is unverified |
| Trade-off | If it works, the entire `AGY_OUTPUT_CONTRACT` prompt-discipline workaround and most of the fail-closed parse machinery become belt-and-braces rather than the only defence |
| Compatibility | Contradicts a load-bearing comment repeated across the codebase, memory, and CLAUDE.md: *"`agy` has NO `--output-schema`"*. That statement is **true as literally written** (the flag is spelled `--json-schema`) but has been carried as "agy cannot enforce output shape", which the help text refutes |
| Risk | **medium** — needs a probe before any design depends on it |

This is orthogonal to A and B: it does nothing for the 8 timeouts and
potentially everything for the 9 parse failures.

## ⚠️ Pitfalls

1. **A green `/hm:health` is not evidence the model works.** The smoke uses
   `SMOKE_PROMPT` — "Do not analyse anything. Return an empty findings array."
   Probe 1 measured that class of prompt at 117s against a 240s cap. So health
   passes on ~49 % margin while any real-sized call fails. CLAUDE.md already
   warns the smoke is *"structurally `invoked`-biased"*; this quantifies why.
   The same reasoning error — reading a green smoke as coverage of the real path
   — is recorded as the thing that hid H1 for its entire lifetime.
2. **Reading `skipped` as "the model refused" or "we were rate-limited".** All
   three causes land in `status: skipped`/`failed`; only `skip_reason`
   distinguishes them, and it is the field an eyeball skips. Aggregate counts
   are actively misleading here.
3. **Aggregating across models.** Combined loss is 21.2 %; per-model it is 2.1 %
   (codex) vs 39.2 % (antigravity). CLAUDE.md records the same trap being hit on
   2026-08-06 with different numbers. The healthy model dilutes the broken one.
4. **Dropping `failed` from the loss rate.** 9 of antigravity's 20 losses are
   `failed`, not `skipped`. A `failed` row means the CLI ran and returned
   something Step 4 cannot consume — that voice is just as absent as a skip.
5. **Assuming flag order is still broken.** `[fail:tooling]
   agy-print-flag-swallows-next-flag` is fixed and probe 6 re-verifies it. Do not
   re-diagnose this as the flag bug.
6. **Assuming the process-level backstop is what fires.** It never has.
   `AGY_TIMEOUT_S=300` sits deliberately above the native 240s so agy's own
   diagnostic wins — the design works, and every timeout row carries agy's
   message rather than ours.

## ❓ Open Questions

1. **Which Flash tier?** `Flash (High)` vs `Flash (Medium)` — only Medium was
   probed (14s on 41 KB). Depth-vs-latency for the voter role is a `plan`
   decision.
2. **Does `agy --json-schema` actually enforce shape?** Unprobed. Decides
   whether Approach C is real or a dead end, and whether the "agy has no output
   schema" claim in CLAUDE.md + memory + three code comments needs correcting.
3. **Should the model be a per-project config or a shipped default?** It is
   already `second_opinion.antigravity.model` in `harness.yaml`, so a local fix
   is one line — but the shipped default in `models.py:467` /
   `second_opinion_invoke.py:28` is what every other consumer inherits.
4. **Should a timeout be retried once at a faster tier?** The invoker has no
   retry path at all (`grep retry` → zero hits). A single fallback retry would
   convert most timeouts into votes, at the cost of complicating the 7-branch
   status matrix.
5. **Should `/hm:health` smoke be sized realistically?** A ~40 KB smoke would
   have caught this on 2026-07-27 instead of on 2026-08-08. Cost: ~4 minutes per
   health run when the tier is wrong, which is arguably the correct signal.

## 📚 Sources

- `agy --help` and `agy models` — live CLI output, 2026-08-08, `/home/noel/.local/bin/agy`
- Live probes 1–6, this session (commands and elapsed times recorded above)
- `.claude/observability/second-opinion.jsonl` — 112 rows, aggregated 2026-08-08

No external web or library sources were needed; the question is answerable
entirely from local telemetry plus controlled probes of the local CLI.

## 🔗 Related Internal Docs

- [[PLAN-second-opinion-multi-model]] — introduced the antigravity voter and the per-model config sub-block
- [[PLAN-second-opinion-invocation-and-slug-cap]] — moved both CLI invocations into `second_opinion_invoke`; commit `b80c3c2c`, two days before the first timeout
- [[PLAN-second-opinion-acceptance-gate]] — the PIDA gate that consumes these findings
- [[REVIEW-second-opinion-invocation-and-slug-cap-2026-07-25]]
- `[[wiki:architecture second-opinion-invoker]]` — the "external contract a rendered prompt executes must be exercisable by a test" rule
- `[[fail:tooling agy-print-flag-swallows-next-flag]]` — the prior agy invocation defect; re-verified fixed here

---

## Appendix — how to diagnose this yourself, in future

Answering "is it quota or something else?" takes two commands.

**1. Read the reason, not the status.**

```bash
python3 -c "
import json, collections
rows=[json.loads(l) for l in open('.claude/observability/second-opinion.jsonl') if l.strip()]
c=collections.Counter((r['model'], r['status'], str(r.get('skip_reason'))[:110])
                      for r in rows if r.get('finding_ref')=='n/a' and r['status']!='invoked')
for k,v in c.most_common(): print(v,'|',k)
"
```

The `skip_reason` string is authoritative and already distinguishes every cause:
`subscription quota reached (resets ~Nh)` = quota; `Error: timeout waiting for
response` = the native print-timeout; `found 0 JSON payloads` = parse.

**2. Probe the CLI directly with a realistic payload.** A trivial prompt proves
nothing (see Pitfall 1) — the smoke passes while real calls fail.

```bash
git log -p -3 -- <some-file> | head -c 40000 > /tmp/p.txt
time agy --sandbox --print "$(cat /tmp/p.txt)" --print-timeout 240s --model "Gemini 3.1 Pro (High)"
time agy --sandbox --print "$(cat /tmp/p.txt)" --print-timeout 240s --model "Gemini 3.6 Flash (Medium)"
```

If both fail with a quota message → subscription. If the Pro tier times out and
Flash returns JSON → model-tier latency, which is what happened here.
