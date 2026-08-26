# BASELINE-DELTA — ci-derived-verification-plan

**Status: MEASURED, not declared.** No figure was predicted before the change. The movement was
found by running `tests/structural/` after the template edit and is recorded after the fact,
which is the weaker of the two shapes and is stated as such rather than presented as a plan
that came true.

**Owning phase: none — this task has no phased PLAN.** It was implemented directly, at the
user's explicit choice of workflow, from `specs/SPEC-ci-derived-verification-plan.md`. Saying
"Phase N" here would be a fabrication for the sake of matching the shape of the documents
around it. The single change that moved the baseline is the one named below.

The rule this document satisfies is `PLAN-surface-ratchet`'s **ADR-010** — a ratchet is never
rebaselined by its own subject. The failure class it names,
`ratchet-rebaselined-by-its-own-subject`, is about the *record* disappearing, not about the
sign of the movement: a net reduction that quietly absorbs a real increase is the same erasure.
There is a real increase here, and it is in the same task as the reduction.

**Current aggregate after this task: `claude` 435437, `codex` 370292.** The `aggregate_chars`,
`payload_digest` and `render_sha` keys all moved; the latter two are mechanical consequences of
regeneration and carry no independent meaning.

### Direction, stated out loud

**`wrapup` got LARGER on both arms — +40 chars on `claude`, +3 on `codex` — while the aggregate
got smaller.** Those are different facts. A reader scanning only the aggregate would conclude
the change cost nothing anywhere; it cost 40 characters of per-turn-injected surface on the
wrapup command, and the reduction hiding that came from `verify`, a different command.

The reduction is also smaller than it looks in round trips. `verify` sheds three charged call
lines on the `claude` arm but **five** on `codex`, and the extra two are not calls anyone made:
`count_round_trips` counts `Bash(` as a substring, so the removed block's commented examples
(`# Rust: Bash("cargo test && cargo check")`, `# Node: Bash("pnpm test && pnpm build")`) had
been charged as round trips for as long as they existed. Removing a comment is not a saving.
The honest saving is **three per command per arm**, and the codex arm's extra two are a
correction to a miscount, recorded here so a later reader does not attribute them to this work.

## What moved, and which change moved it

| Key | Before | After | Δ | Cause |
|---|---|---|---|---|
| `claude` aggregate | 435526 | 435437 | **−89** | net of the rows below |
| `codex` aggregate | 370455 | 370292 | **−163** | same, codex surfaces |
| `verify` `chars` | 24673 | 24544 | **−129** | four example gate commands → one `verification_plan commands` call |
| `verify` `round_trips` | 15 | 12 | **−3** | same: four charged `!` lines → one |
| `wrapup` `chars` | 46043 | 46083 | **+40** | same swap, but the replacement prose is longer than wrapup's terser original block |
| `wrapup` `round_trips` | 28 | 25 | **−3** | same: four charged `!` lines → one |
| `hm-verify` `chars` | 22072 | 21906 | **−166** | same swap, codex arm |
| `hm-verify` `round_trips` | 14 | 9 | **−5** | −3 real, −2 from commented `Bash(` examples the substring rule had been charging |
| `hm-wrapup` `chars` | 44249 | 44252 | **+3** | same swap, codex arm |
| `hm-wrapup` `round_trips` | 28 | 23 | **−5** | same −3 / −2 split as `hm-verify` |

**One change moved every row.** `SPEC-ci-derived-verification-plan` replaces the shipped EXAMPLE
gate commands in `verify` and `wrapup` — `pytest -q` / `pytest -x`, `ruff check src/ tests/`,
`ruff format --check src/ tests/`, `mypy --strict src/` — with a single
`hm verification_plan commands --root .` call that derives the gates from the project's own CI.
No other command was expected to move, and none did.

Why `wrapup` grew while `verify` shrank, given the same swap: the two blocks were not the same
size to begin with. `verify`'s original carried a nine-line prose paragraph about the runner
recipe that the replacement compresses; `wrapup`'s original was four commented lines and almost
no prose, so the replacement's degraded-fallback instructions are net new text. The +40 buys the
branch a reader needs when the derivation fails, which the old block did not need because it had
no derivation to fail.

## Round trips

The per-command table in `test_roundtrip_budget.py` was re-baselined for `verify` (15 → 12) and
`wrapup` (28 → 25) with the reason inline at each row. No other command's count moved. The codex
arm has no entry in that table — it is covered by `surface_baseline.json` only, which is why the
comment-charging correction above appears here and not there.

## What a reader should check if this document looks wrong

There is exactly one cause, so the check is a single revert: restore the two `{% if is_codex %}`
example blocks in `templates/stages/verify.md.j2` and `templates/stages/wrapup.md.j2`, re-render,
and all ten rows should return to their "Before" values. If a row moves that the revert does not
restore, this attribution is incomplete and that row is the finding.

One consequence is worth flagging rather than leaving for a later reader to discover.
`test_review_verify_uses_dep_map::test_the_out_of_scope_wrapup_full_run_survives` asserts that
`uv run pytest -x` survives in the rendered wrapup, as a vacuity guard proving the neighbouring
ban on full-suite runs is scoped to review's verify step rather than blanket. After this change
wrapup's real full-suite run is whatever the project's CI test gate is, resolved at runtime; the
literal the guard matches is now the **degraded fallback**, not the primary path. The assertion
was left untouched — amending it to match this change is
`[fail:test] assertion-amended-to-match-the-fix` — but the witness it watches is weaker than it
was, and that is a cost of this change, not a property of it.
