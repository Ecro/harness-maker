# SPEC-spec-md-source tier-1 bench (2026-11-28)

Tier 1, 5 tasks x 3 runs, Sonnet 5.5, no judge. hm-base = 32aff696; hm-new = branch hm/spec-md-source (unmerged)
(first batch, the verdict); hm-fix = the same branch after the property-fields fix (post-verdict
batch, about one hour later). Not merged: the DRI chose "record only" (2026-11-28 card) after this result. Rows were reduced by
a per-run transcript script (main-session Write/Edit/redirect to `*.machine.yaml`, code-reviewer Reads of it, output tokens per assistant message).

| arm | runs | hidden pass | main writes machine.yaml | reviewer Reads of machine.yaml | mean main output tokens | mean cost | mean wall |
|---|---|---|---|---|---|---|---|
| hm-base | 15 | 14/15 | 15/15 | 5 of 14 reviews | 12,198 | $0.387 | 122.2 s |
| hm-new | 15 | 15/15 | 0/15 | 0 of 14 | 13,983 | $0.442 | 138.4 s |
| hm-fix | 15 | 15/15 | 0/15 | 0 of 15 | 13,431 | $0.417 | 132.3 s |

AC-006 verdict (first batch): **missed**. Met: no yaml writes (0 ≤ 2 allowed), reviewer reads
0 ≤ 2, passes 15 ≥ 14. Missed: mean main output tokens 13,983 vs 12,198 (+15%). Cost +14%, wall
+13% (no bar).

Why it costs more:
- The model now writes SPEC.md with a yaml block per AC: about 8.8k chars of SPEC writes per run
  versus about 7.1k for base's SPEC.md plus machine.yaml together. The AC prose did not shrink when
  the fields moved into it.
- About 3 more tool calls per run (`sync`, an extra `finalize`).
- First batch only: 6 of 15 runs failed validate on a property AC with no `observable_output`
  (the block example did not list the property fields) and one block did not parse; each cost a
  fix and a rerun. The fix batch removed those (1 failed result in 15 runs) and cut the gap to
  +10% output, +8% cost.
- Reviewer subagent cost per run did not move: base $0.063, new $0.063, fix $0.067.

The 2026-11-28 estimate (about −3%) assumed the yaml chars would disappear; they moved into
SPEC.md and grew.

What was built and dropped: `hm spec_machine sync` (machine.yaml generated from a fenced yaml
block under each `### AC-NNN:` heading and the Irreversible Decisions table), cross-validate
rule 7 (block vs yaml drift), `finalize` checking the SPEC.md-derived yaml, spec Step 3.5 folded
into Step 3, and the code-reviewer told not to read machine.yaml.

Lesson: estimate a "write it once" cut from what the model will write after the change, not
from what disappears. A machine copy the CLI generates is only cheaper if the human copy does
not grow to carry the same fields.
