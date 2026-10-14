<!-- @hm:autopilot-advance -->
## Auto-advance check (autopilot — Claude Code only)

Before the STOP banner below, check whether this session runs under **autopilot** (live
auto-advance, ADR-005) — **Claude-Code-only**: it needs the `.hm-autopilot` marker (armed
by the picker) and the `Skill` tool. **This section is a NO-OP** — fall straight through
to the STOP banner, running nothing below — **if any of: no `Skill` tool (Cursor/Codex),
no active marker, or loop-mode is on for THIS session (a `.claude/.hm-loop-*` marker
matches `$HM_SESSION_ID`, or a legacy `.hm-loop-active` exists).**

**Step 1 — mandatory gate FIRST (absent-case = STOP).** Evaluate THIS stage's gate
*before* anything else: Read the SPEC's acceptance with `hm spec_machine approval-status --root . --slug <slug>`: pass --judgment-gate clear when state is approved or exempt, blocked when malformed, pending otherwise. The boundary re-derives the same verdict from the SPEC, so a clear the SPEC does not support never advances. At auto_full a pending is answered WITHOUT writing an approval — the land hold covers the SPEC's irreversible decisions.
Do NOT stop here and do NOT run `gate-blocked`. Classify the gate and carry the verdict into
Step 2, which records the stop for you. Exactly one of:
- **`clear`** — nothing pending.
- **`pending`** — a genuine judgment is unresolved: a question with a defensible answer.
  Stops at `gated`/`auto_safe`; `auto_full` answers it.
- **`blocked`** — the failing half is a **quality threshold**, not a question (a failed grade,
  a failed check). **No level clears it, `auto_full` included.**

**Unsure at any boundary → pick the more restrictive value.** The ladder is
`clear` < `pending` < `blocked`. That direction is deliberate: `pending` is the one value
`auto_full` clears, so resolving uncertainty downward routes a possible failure past the gate.

Omitting the flag entirely is **not** `pending` — it halts at every level, including
`auto_full`, and reports a stale render. Say nothing only when you mean "I did not classify".

**Step 2 — boundary check.** Run the deterministic check
(it enforces the Phase-5 runaway caps + kill switch, and on proceed records the advance it
authorizes — so it must run only after Step 1 clears):

If this stage has a slug, **append** it to the command below in single quotes — e.g.
` --slug 'my-task'`. Never a shell expression or a bracketed placeholder. Omit it
otherwise; the marker keeps the earlier stage's slug.

**Also append your Step 1 verdict** — exactly one of ` --judgment-gate clear`,
` --judgment-gate pending`, or ` --judgment-gate blocked`. A literal word, never a
placeholder. **Omitting it is not a way to say `pending`**: an absent verdict halts at every
level, `auto_full` included, and reports a stale render.


!uv run --with {src} hm autopilot_caps boundary --root . --current spec --session-id "$HM_SESSION_ID" --step-cap 20 --time-cap-min 300

Read the JSON:
- `proceed: false` → **STOP** (print the banner) — **except `bad_slug`**. `step_cap`/
  `time_cap` = a runaway cap fired (`halted_cap` logged, marker cleared); `kill_switch` =
  autopilot off/expired; `merge_gate` = the next stage is human-gated (e.g. wrapup's
  merge/land — the marker was cleared, so invoke `/hm:wrapup` manually); `unknown_stage` =
  `--current` not in the pipeline; `pipeline_complete: true` = the pipeline finished and
  the marker was cleared.
  `judgment_gate` = the gate was `pending` at a level that does not
  clear it, or `blocked` (which no level clears). The marker was **preserved** and the stop
  was recorded; resolve the gate and re-run.
  **`bad_slug` is yours to undo**: the `--slug` you passed is invalid; nothing was
  authorized. Do NOT print the banner — re-run with a corrected slug, or no flag.
- `proceed: true` → **auto-advance**: invoke `Skill(hm:<next_stage from the JSON>)` with
  the JSON's `task_slug` as its argument (omit when `null`), instead of the STOP banner.
  **This supersedes this stage's earlier "Stage terminal … STOP"** — that governs the
  gated path, and `proceed: true` IS the authorization it asks for. `task_slug_source:
  "persisted"` means the slug came from an earlier stage — name it before invoking, so
  another task's slug cannot advance silently.
- `judgment_auto_answered: true` → the level cleared a judgment gate for you. **Do what
  `judgment_directive` says before advancing.** An auto-answer that is not written down is
  an unauditable skip of a human decision — the record is the only thing that makes this
  level reviewable after the fact.

<!-- @hm:/autopilot-advance -->
