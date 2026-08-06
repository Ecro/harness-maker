---
type: review
task_slug: onboarding-interview-ux
status: APPROVED
created: 2026-08-06
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: onboarding-interview-ux
  computed_at: 2026-08-06T00:00:00Z
---

# REVIEW — onboarding-interview-ux

## 🎯 Round 1 Summary

**Grade: D** (1 consensus-passed P0). Voter pool N = 4 (code-reviewer, security-reviewer,
codex, antigravity), K = 2.

The change adds installed-CLI detection and a disclosure table so the fresh-install fast path
stops hiding what it decides. The P0 is that the disclosure table itself was **false about the
highest-consequence axis it discloses** — the defect class this work exists to remove,
reproduced inside the fix.

## 🔍 Drift Findings

None. Every changed path maps to a PLAN phase scope. Two deviations were recorded in the PLAN's
execution notes rather than as drift: Phase 6 shipped implementation before its render tests,
and Phase 8's docs cleanup was cut to the READMEs after measurement showed ~40 sites rather
than the ~11 the PLAN estimated.

## ✅ Consensus Findings

### P0 — `commands/make.md:227`: the disclosure table stated the opposite of the shipped default

`[2/4]` — code-reviewer and security-reviewer independently, same file, same line, same tier,
CONCLUDE aligned. Confirmed by direct measurement: rendering a real fresh install produced
`autonomy.level: "auto_safe"`.

| | Table said | Actually rendered |
|---|---|---|
| `autonomy.level` | `gated` (off) | `auto_safe` |
| persistence | off | `true`, re-armed by a SessionStart hook every session |

A user taking the default path was told auto-advance was off while the harness shipped it on.
The structural gate could not catch it: `test_the_disclosure_table_includes_the_axes_dispatch_argv_cannot_carry`
asserted `re.search(r"autonomy|autopilot", summary)` — presence, not truth. That is the shape
`test_baseline_delta_attribution.py`'s own docstring names as a defect ("checking that text
EXISTS rather than that it is TRUE").

**Fixed** in round 2. The row now states `auto_safe` / persistent `true`, names the SessionStart
re-arm, and names the mandatory gates that still stop. The second site (`gated` (off, default)
in the Full-setup question) was corrected too. A new arm,
`test_the_disclosed_autonomy_value_is_the_one_a_fresh_install_actually_renders`, reads
`AutonomyConfig()` and asserts the row states the real default — verified by the round-2
reviewer to fail on a revert.

## ⚠️ Weak Consensus

None. No pair reached surface match with diverging CONCLUDE.

## 📝 Manual-Only Findings

Single-source or cross-tier, so none lowered the grade. All were verified and fixed anyway
except where noted.

| Severity | Source | Finding | Disposition |
|---|---|---|---|
| P1 | security-reviewer | `permissions.deny_dangerous` row pointed at `/hm:configure`, which has no permissions dimension | **Fixed** — cell now says hand-edit `.claude/harness.yaml` and states the absence explicitly. Verified: `configure.md.j2` has zero `permissions` occurrences, `cli.py` has no `--deny-dangerous`. codex raised the same defect at P2 (`4cd1ee7d`) — different tier, so not a consensus candidate, but two independent voices on the substance. |
| P1 | security-reviewer | Second-opinion consent prompt did not disclose that the diff leaves the machine | **Fixed** (round 3). CLAUDE.md's posture is "100% local telemetry, no external transmission"; this is the one exception and the consent screen was silent about it. Round 2 caught that the round-2 fix had silently no-op'd — see Iteration 2. |
| P1 | code-reviewer | `configure.md.j2`'s `detect-tools` call lacked the `uv run --with` prefix every other call in the file carries | **Fixed** — would have been `command not found` in the default install shape, with no degrade clause (unlike health's). Round 3 moved it into a fenced `!` block after round 2 found the inline form is not autorun. |
| P2 | codex | Cost stated as "one extra CLI call per review"; it is one per enabled model, on every review AND every plan validation | **Fixed** (round 3), and further qualified: Production every time, Side only on high-diff. |
| P2 | code-reviewer | `surface_baseline.json`'s `render_sha` names the previous freeze point | **Accepted, not fixed.** `assert_sha_is_durable` refuses to write a task-branch SHA, so "regenerate honestly on a task branch" is not expressible. Recorded rather than papered over. |
| P2 | code-reviewer | The consensus/caching prompt filter had three unreachable arms after `rstrip()` | **Fixed** — filter now matches un-stripped, plus an arm proving the `[Y/n]`-style prompt is captured. |
| P2 | security-reviewer | "destructive-command baseline is NOT applied" is target-qualified | **Accepted.** Round 2 downgraded its own concern: the row is exactly right for the default `claude-code` target and *understates* protection for cursor/codex. An under-claim in a transparency table is the safe direction. |
| P2 | security-reviewer | `--locale` is unvalidated free text reaching a rendered shell argument | **Out of diff**, confirmed by round 2. Pre-existing shape; recorded as a follow-up. |

## 🤝 Disagreements

`permissions.deny_dangerous` was raised at **P1** by security-reviewer and **P2** by codex. Step
4a forbids bridging tiers, so they stayed independent rather than forming a consensus cluster —
which is why a defect two voices confirmed did not move the grade. Recorded because the rule's
consequence is easy to misread as "only one reviewer found it".

## 🧊 Cross-model findings (frozen @ round 1)

Both models `status: invoked`. Four findings; two accepted, two refuted with oracle evidence.

| id | model | severity | disposition | oracle |
|---|---|---|---|---|
| `4cd1ee7ddf6f1d4f` | codex | P2 | **accepted** | `grep -c "deny_dangerous\|permissions" configure.md.j2` → 0; `grep -c "deny.dangerous" cli.py` → 0 |
| `b90e50e374befde1` | codex | P2 | **accepted** | `review.md.j2` and `plan.md.j2` both carry a per-model invocation section; this session itself made 2 calls at plan and 2 at review |
| `384b13558ada4ffd` | antigravity | P1 | **rejected** | Claim: `hm cli detect-tools` is a hallucinated command. `uv run --with . hm cli detect-tools --json` → `{"codex":{"installed":true},…}`. `hm cli <cmd>` is the established convention (6 prior uses in `configure.md.j2` alone). The initial "No such command" came from `--with $HOME/harness-maker` resolving the base checkout, which predates this change — a test artifact, not a defect. |
| `2599c663725b90ed` | antigravity | P1 | **rejected** | Claim: omitting the flag on decline preserves previously-enabled models. §4 runs only when `.claude/harness.yaml` is absent (`make.md:96` routes an existing file to §3 re-render), so there is no prior value to preserve. |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 9         | —   |
| 2         | —     | 4             | 5         | 3   |
| 3         | A     | 5             | 2         | 0   |

### Iteration 2 (Grade: D → re-review)
Fixes applied: 4

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P0 | autonomy row stated `gated`/off; real default is `auto_safe`/persistent | commands/make.md:227 | Applied · caused_by=none |
| 2 | P0 | same false claim, Full-setup question | commands/make.md:346 | Applied · caused_by=none |
| 3 | P1 | `deny_dangerous` pointed at a non-existent `/hm:configure` dimension | commands/make.md:232 | Applied · caused_by=none |
| 4 | P1 | `detect-tools` call missing the `uv run --with` prefix | configure.md.j2 | Applied · caused_by=none |
| — | P1 | egress disclosure | commands/make.md:262 | **Silently no-op'd** — `str.replace` pattern omitted two leading spaces; the script printed success unconditionally. Caught by round 2. |

Remaining: 5 | New issues introduced: 3 (the no-op above, plus two P2s round 2 raised against the round-2 text)

### Iteration 3 (Grade: → A)
Fixes applied: 5

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | egress disclosure, re-applied with `Edit` (errors on no-match) | commands/make.md | Applied · caused_by=#none (iteration-2 no-op) |
| 2 | P2 | cost line ignored the Side preset's high-diff gate | configure.md.j2 | Applied · caused_by=#4 |
| 3 | P2 | inline `!uv run` is not autorun; bash reads `!uv` as a command word | configure.md.j2 | Applied · caused_by=#4 |
| 4 | P2 | prompt-filter arms unreachable after `rstrip()` | test_interview_second_opinion_prompt.py | Applied · caused_by=none |
| 5 | — | round-trip budget re-baselined (configure 3→4, total 130→131) with named cause | test_roundtrip_budget.py | Applied · caused_by=#3 |

Remaining: 2 (both accepted, documented above) | New issues introduced: 0

Final grade: A
Iterations used: 3 / 3
Exit reason: converged
Status: APPROVED
human_review_needed: false
Counters: unreviewed 0 · prior-fix 2 · unattributed 0

## Notes for the next reader

**Six gates fire when a rendered template changes**, not the one the PLAN anticipated:
aggregate surface ratchet · baseline-delta attribution document · command-surface registry ·
synthesize snapshots · round-trip budget · render fixtures. Four of the six were discovered by
tripping them.

**Two silent-success failures happened in one session** and neither was caught by the thing
that claimed success: a background `pytest` reported exit 0 on `rc=1`, and a `str.replace`
patch script printed "patched" after matching nothing. Both were caught only because something
downstream re-read the actual state. Prefer tools that fail loudly (`Edit` over `str.replace`,
an `rc=` sentinel over a notification's exit code).
