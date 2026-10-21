---
type: research
task_slug: hm-cost-p3
created: 2026-10-21
summary: Where the hm arm's tier-1 spend goes after hm-cost-p2 (transcript $0.786/run, 12.21x plain), by stage, subagent and call, from the counted AC-009 run's transcripts.
---

# RESEARCH — hm-cost-p3

## Source

The counted SPEC-hm-cost-p2 AC-009 run: `/var/tmp/hm-eval-t1-p2c` (harness 94a6d1f32935, squash-landed as
022d6f2a), archive `~/hm-eval-archive/hm-eval-t1-p2c-2026-10-21.tgz`, tier 1, claude-sonnet-5-5, 5 tasks
× 3 runs per arm, 15/15 hidden-test passes in both arms. Turns are priced with the bench's own
`economics_source.load_turns` + `economics.price_turn` (the `transcript_cost_usd` definition). The bench
runs each stage as a resumed turn of one session: `/hm:spec`, the DRI's "I approve…" reply, `/hm:execute`,
`/hm:wrapup`.

## Spend by bucket (hm arm, mean per run, transcript price $0.786)

| bucket | $/run | share | API calls | output $ | cache-read $ | cache-write $ |
|---|---|---|---|---|---|---|
| main: execute | 0.267 | 33.9% | 13.7 | 0.077 | 0.124 | 0.066 |
| main: approval turn (unattributed) | 0.155 | 19.8% | 7.0 | 0.060 | 0.053 | 0.043 |
| main: spec | 0.126 | 16.1% | 4.5 | 0.041 | 0.020 | 0.066 |
| main: wrapup | 0.112 | 14.2% | 5.1 | 0.024 | 0.061 | 0.026 |
| sub: code-reviewer | 0.073 | 9.2% | 3.3 | 0.033 | 0.006 | 0.034 |
| sub: spec-validator | 0.053 | 6.7% | 2.4 | 0.034 | 0.004 | 0.015 |

(Call counts per bucket come from the pricing loader, which groups records by API message id; a second
count by stage prompt boundaries gives spec 7.3, approval 2.4, execute 15.5, wrapup 5.1 — the two
differ in where the approval turn's follow-on calls are attributed.)

## Findings

1. **Fixed harness load is small.** First-call context: hm 22.0k tokens, plain 17.5k (+4.5k: CLAUDE.md,
   skills, the stage command).
2. **Context accumulates across stages.** First call of each stage: spec 22k → approval 29k → execute 39k
   → wrapup 57k tokens. Most of the 1.34M cache-read tokens per run is that carry re-read on every call.
3. **The approval turn is 20% of spend.** The bench DRI says "take the option you recommend for each open
   question… stamp". The agent then rewrites the SPEC (a ~3.1k-char python edit) and re-runs check and
   approve. Open Questions are filled mostly from spec-validator critiques: spec Step 4.6 records every
   critique there, and Step 5 leaves `status: draft` while Open Questions is non-empty.
4. **The gate runs 2.6 times per run.** `hm check` 1.5× in execute (Bind, plus after review fixes) and
   1.1× in wrapup Step 1. Execute writes the REVIEW doc after its last `hm check`, so the tree wrapup
   gates differs from the one execute gated only by that doc. No verdict cache exists in `check.py`.
5. **Execute makes 15.5 calls, 12.5 of them Bash** (5.3 begin with a bare `cd`), at roughly $0.017 per
   call with 40–60k context.
6. **Files are written through Bash heredocs**, not Write/Edit (≈1 Write/Edit per run): SPEC + yaml ≈ 6k
   chars in spec, tests + code ≈ 6k in execute. Visible output is ≈ 9k of the 26.9k output tokens; the
   rest is thinking and subagent output (thinking text is empty in the transcripts).

## Estimated savings (to verify by re-measure)

| cut | estimate | basis |
|---|---|---|
| A: defaults written into the SPEC, approval = stamp | ≈ $0.11 | approval turn $0.155 → a 1–2 call stamp at ~30k context |
| B: reuse an unchanged-tree gate verdict; fewer execute calls | ≈ $0.10 | wrapup gate rerun + ~5 execute calls × $0.017 |
| C: no spec-validator on small tasks | ≈ $0.05 | its own $0.053, plus fewer Open Questions feeding A |

A+B+C ≈ $0.26 → ≈ $0.52/run, ≈ 8x plain ($0.064). Reaching 5x needs fewer stages or documents for small
tasks, which trades away quality devices — out of scope here.

## Measured after the change (2026-10-22)

Run `/var/tmp/hm-eval-t1-p3` (harness cdf28dce3b12, `--jobs 4`, archive
`~/hm-eval-archive/hm-eval-t1-p3-2026-10-22.tgz`): transcript ratio **11.36** (CLI 10.27), hidden pass
15/15 vs 15/15. The pre-registered 10.0 bar (SPEC AC-005) is **missed**.

| bucket | before $/run | after $/run | Δ |
|---|---|---|---|
| approval turn | 0.155 | 0.117 | −25% (A) |
| spec | 0.126 | 0.146 | +16% (A's defaults are now written in the spec stage) |
| execute | 0.267 | 0.256 | −4% (calls 13.7 → 14.3: the batching rule did not cut calls) |
| wrapup | 0.112 | 0.102 | −9% (`--reuse` hit in 14 of 15 runs) |
| code-reviewer + spec-validator | 0.126 | 0.126 | 0 |
| total | 0.786 | 0.746 | −5% |

What the estimate got wrong: a reused gate saves test wall time, not tokens. The gate's tokens were one
compact JSON line; wrapup's spend is the 54–57k context re-read on each of its ~5 calls. The approval
turn's saving was partly moved into the spec stage, which now writes the defaults the approval turn used
to write. Remaining cost is carry (cache-read 1.31M tokens/run), which only fewer calls or fresh
per-stage sessions move.

## Method

```python
# per bucket: main turns keyed by attribution_skill, subagent turns by attribution_agent
turns = economics_source.load_turns(work, transcript_root=tr_root).turns
for t in turns:
    c = economics.price_turn(t)
    key = ("sub:" + t.attribution_agent) if t.is_sidechain else ("main:" + (t.attribution_skill or "?"))
```
Tool and verb counts: main-chain `tool_use` blocks deduplicated by id, staged by the `<command-name>/hm:…`
user prompts and the "I approve" reply.
