---
type: review
task_slug: maker-digest-bash-step
created: 2026-11-23
spec: "[[SPEC-maker-digest-bash-step]]"
plan: "[[PLAN-maker-digest-bash-step]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: 11 findings (1 major already fixed, 4 minor, 6 nit). Ten accepted and fixed, one pre-existing item left out of scope (F11); nothing unresolved."
---

# REVIEW — maker-digest-bash-step

One code-reviewer round on the uncommitted diff. The reviewer mutation-tested the template in a
scratch copy: re-adding a Claude `!` line, an inline `!`, Codex back to "Run once", a weakened
phrase, Codex given `${CLAUDE_SESSION_ID}` and a second digest block were all killed. No
`Do not change` path was crossed. The live boundary test was re-run after the fixes: both arms pass
(trusted: digest ran with the CLI's session id; `CLAUDE_CODE_IGNORE_PERSISTED_TRUST=1`: Maker
reached the model and the denied command named the digest with the substituted id).

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | major | tests/render/test_ask_less.py:235 | The longer introducing sentence grew the Codex Maker past the ask-less growth allowance (753 > 750); the PLAN exit command did not run that test. Fix: dropped "; failing → say so" (the fallback bullet already covers failure); PLAN exit now lists every test that reads the Maker render | accepted | SPEC-ask-less AC-007 |
| F2 | minor | README.md:432, README.ko.md:354 | Still said Claude Code injects the digest at load. Fix: "first Bash step on every call, on both targets" | accepted | docs accuracy |
| F3 | minor | docs/ARCHITECTURE.md:47 | Same stale "injected at skill load". Fix: reworded | accepted | docs accuracy |
| F4 | minor | docs/reference/world-model.md | Said Maker "then says the digest was denied", which the skill no longer asks for. Fix: labelled as observed model behaviour; the skill only names the `work-docs/`/`specs/` fallback | accepted | SPEC Intent |
| F5 | minor | SKILL.md.j2 | The run-first step sat inside `## Briefing — read-only`, after "Pick ONE row", so a Start or Goals route could read it as briefing-only, and "Write nothing here" read as global. Fix: step moved above `## Pick the route` (char-neutral) | accepted | PLAN risk line |
| F6 | nit | tests/render/test_render_maker_digest_bash_step.py | No-injection check only caught lines starting with `!`. Fix: also any `` !` `` on a digest line | accepted | SPEC AC-001 |
| F7 | nit | docs/reference/world-model.md | "both targets" block shows the Claude form only. Fix: labelled, Codex form named | accepted | style |
| F8 | nit | tests/integration/test_boundary_maker_default_permissions.py | `tool_input` null would raise `AttributeError`. Fix: `isinstance(..., dict)` filter | accepted | robustness |
| F9 | nit | tests/render/test_render_maker_digest_session_id.py, test_render_maker_front_door.py | Docstring and section comment still described an injected command. Fix: reworded; test ids kept | accepted | SPEC Refinement Decisions |
| F10 | nit | docs/reference/world-model.md | `pre-existing:` test table said "Maker ≤ 4,500 chars"; the cap is 4,689. Fix: corrected | accepted | CLAUDE.md World model |
| F11 | nit | src/harness_maker/wrapup_brief.py:201 | `pre-existing:` docstring mentions a `!` line no template has | pre-existing | outside PLAN scope; separate cleanup |

Size after the fixes: the Claude Maker passes the 4,689-char cap test at its pinned `$HOME` path
(the reviewer measured 4,682 before 19 chars were dropped; HEAD was 4,677). With this container's
absolute checkout path it is 4,691, the same over-cap gap on long paths already logged under
HR-022.
The cross-model second opinion was not run (no `codex` or `antigravity` CLI in the
container).
