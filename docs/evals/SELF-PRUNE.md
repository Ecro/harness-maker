# Self-prune loop

When a new default model ships, hm measures which of its own instructions the model no longer
needs and **proposes** cuts. It never edits templates or opens a PR of cuts: the DRI picks a
proposal and it goes through `/hm:` like any change (SPEC-self-prune-loop, DRI decision
2026-11-23).

## Trigger

- **Detection** runs in the weekly research routine (Monday 08:41 KST): if the default model is
  new, `uv run python scripts/self_prune.py status --model <id>` prints `unmeasured` (exit 1),
  and the routine fires the `hm-self-prune` trigger. Detection costs nothing.
- **Manual**: the DRI asks for a prune run in the project; the same trigger fires.
- One run per model: `status` reads `docs/evals/prune-ledger.jsonl`.

## Run (cloud Claude Code session, never GitHub Actions)

The bench needs `claude` on PATH, which CI does not have. Keep the base checkout untouched while
it runs. Container settings: `IS_SANDBOX=1` with `--pass-env IS_SANDBOX`, `--out` under
`/var/tmp`, a scratch `CLAUDE_CONFIG_DIR`.

1. **Candidates (at most 3).** Read the rendered harness of the bench (`bench_light_lane.py`
   renders Side with claude-code) and the TUNE/HOST entries of `step_sensitivity.py`, previous
   `hold` rows in the ledger, and `RESEARCH-opus55-cuts.md` Group B. Pick blocks this model plausibly
   no longer needs, weighted by tokens. Write `candidates.json`:

   ```json
   {"candidates": [
     {"id": "drop-verify-plan", "rationale": "format check the CLI already does",
      "detectable_by": ["tier-2 hidden tests (PLAN fields drive scope)"],
      "edits": [{"path": ".claude/commands/hm/execute.md", "drop_heading": "## Step 0.3"}]}
   ]}
   ```

   `edits` hold `drop_heading` (one section, up to the next heading of the same or higher level)
   or `old`/`new` (text that occurs exactly once; a rendered knob value is ablated this way).
   `detectable_by` names the bench cells that can fail the way the block prevents; leave it empty
   when none can, and the verdict can be at most `hold` ("priced, not valued").
2. **Plan**: `uv run python scripts/self_prune.py plan --candidates candidates.json --out
   /var/tmp/prune/variants`. It refuses edits inside the protected sections (per-task worktree,
   TDD RED gate, SDD, human approval, IRR lock, understanding-delta summary) and edits that do not
   apply.
3. **Baseline**: `INTEGRATION=1 uv run python scripts/bench_light_lane.py run --tier all --arms
   plain,hm --runs 3 --model <id> --judge-model <id> --pass-env IS_SANDBOX
   --total-budget-usd 60 --out /var/tmp/prune/base`.
4. **One run per candidate**: `... run --tier 2 --arms hm-variant --variant
   /var/tmp/prune/variants/<cid>.json --runs 3 --model <id> --judge-model <id> --pass-env
   IS_SANDBOX --total-budget-usd 35 --out /var/tmp/prune/<cid>`.
5. **Decide**: `uv run python scripts/self_prune.py decide --baseline /var/tmp/prune/base
   --candidate /var/tmp/prune/<cid> [...]`. It appends one ledger row per candidate and prints
   the proposal table.
6. **Report**: put the table in the weekly report; one decision card when a candidate is
   `adopt`. Commit only the ledger rows (a docs PR).

## Guard rule (tier 2, candidate vs the same run's hm baseline)

| Verdict | When |
|---|---|
| reject | solved count or trap catches fell |
| hold | judge overall fell by more than 0.3, cost fell by less than 3%, stalls rose, a judge score is missing, `detectable_by` is empty, or the two arms ran different (task, rep) cells (a budget-capped run) |
| adopt | none of the above |

## Cost

About $150 per model on Opus 5.5 (estimate from the 2026-11-17 tier-1 run: plain $0.19, hm
$1.19 per run): baseline about $57, each candidate about $31, judge about $3. It comes out of
subscription usage; a run stopped by a usage limit resumes with the same `--out`.

## Limits

- Tier 2 has n=21 runs per arm; "any drop rejects" is conservative on purpose.
- One model is measured: a cut is not validated for users on a weaker model.
- The bench renders the Side preset; Production-only sections are not measured.
