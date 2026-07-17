---
type: research
task_slug: make-ux-gaps-2026-05
status: complete
created: 2026-05-10
tags: [harness-maker, research, ux, install, interview, update, configure]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - RESEARCH-harness-gap-cot-2026-05.md
  - PLAN-plugin-vs-generator-2026-05.md
summary: "5 gaps: AskUserQuestion interview, preview/dry-run, post-install summary, broken /hm:make update ref, missing /hm:configure"
---

# RESEARCH — make UX gaps: install, configure, update experience

## 🎯 Recommended Direction

Sequentially close 5 concrete UX gaps identified below. None require architectural rewrites — they are additive or corrective changes to existing files. Highest leverage: (1) fix the broken update-notification command reference immediately, then (2) add `AskUserQuestion`-based interview to `/harness-maker:make`, then (3) add `/hm:configure` + `/hm:make` to the installed harness.

---

## 🔍 Refinement Decisions

No `--deep` flag — topic was specific enough. User explicitly named five concern areas: install simplicity, settings preservation, pre-install preview, post-install summary, removal, user-friendly interview with more configs, update notification correctness, and easy reconfiguration.

---

## 🛠️ Gap Analysis

### GAP 1 — Update notification references a non-existent command

**Evidence (code):** `hooks/sessionstart_drift.py` emits:

```
"Run /hm:make --update for a silent re-render, or /harness-maker:make for a full interactive run."
```

But `/hm:make` is **NOT generated** in the user's harness. The installed commands under `.claude/commands/hm/` are: `exec-rev`, `exec-rev-wrap`, `exec-rev-wrap-ver`, `execute`, `plan`, `research`, `review`, `spec`, `verify`, `wrapup`, `loop`, `refresh`, `ai-readiness`. No `make.md`.

So when a user gets the drift notification and types `/hm:make`, they get "command not found" — the UX breaks at the most critical moment.

**Root cause:** The drift message was written for a future state where `/hm:make` would be a generated slash command; that command was never added to `synthesize.py`.

**Fix options:**

| Option | Approach | Trade-off |
|--------|----------|-----------|
| A | Fix drift message → only reference `/harness-maker:make` | Immediate 1-file fix; no new command |
| B | Add `/hm:make.md.j2` to generated harness (calls `harness-maker make --update`) | User can type `/hm:make` from their project — most ergonomic |
| C | Both: fix message + generate `/hm:make` | Best UX; adds one template file |

**Recommendation:** Option C. The generated `/hm:make` should call `harness-maker make --update` (silent re-render) and add a note explaining `/hm:make --reinterview` for full reconfiguration.

**Risk:** Low. The drift hook already exists; adding one command template and fixing one string is minimal surface area.

---

### GAP 2 — Interview runs from CLI (non-TTY = silent defaults), not via AskUserQuestion

**Evidence (code):** `cli.py` line: `effective_autoloop = autoloop or (not sys.stdin.isatty())`. When the `/harness-maker:make` plugin command calls `harness-maker make` from Claude Code's slash-command context, stdin is not a TTY → `autoloop=True` silently → no interview at all.

So: the user types `/harness-maker:make`, and the CLI immediately renders with preset defaults, emitting "non-tty stdin detected; using --autoloop defaults". There is effectively **no interactive interview** when running from Claude Code.

**Evidence (code):** `CLAUDE.md §CLI vs slash command 책임 분리`: "CLI 에 `input()` / `AskUserQuestion` 박지 말 것 — 슬래시 명령 컨텍스트에는 stdin 이 안 통해 hang."

The correct architecture is already documented: slash commands should use `AskUserQuestion` → map answers to CLI flags → invoke CLI with those flags. The existing `interview.py` is the right logic; it just needs to be surfaced as `AskUserQuestion` calls in the slash command template, and the answers passed as `--preset`, `--locale`, `--dev-mode`, `--targets` etc. overrides.

**What currently cannot be passed as CLI flags (gaps in `_apply_dimension_overrides`):**
- `grade_threshold`, `auto_fix`, `max_review_rounds` — no `--grade-threshold` etc. flags exist
- `domains` — no `--domains` flag
- `mechanical_checks` — no flag
- `mcp_servers` — no flag (complex)
- Reviewers enabled list — no flag

So even if the slash command did `AskUserQuestion`, the answers for the above can't be passed to the CLI yet.

**Fix approach (two-layer):**
1. **Layer 1 (minimal):** Rewrite `/harness-maker:make` command to use `AskUserQuestion` for the current 8-question interview (locale, targets, preset, dev_mode, workflows, consensus, caching, ref_folders), map answers to existing CLI flags, run `harness-maker make --preset=... --locale=... --targets=... --dev-mode=...`. Covers the core interview immediately.
2. **Layer 2 (extended):** Add CLI flags for `--grade-threshold`, `--auto-fix`, `--domains`, `--mechanical-checks`, surface them in the interview. These are all single-field configs that map cleanly to flags.

**Configurations that ARE valuable to interview but NOT yet covered:**
- `grade_threshold` — "How strict should code review be? A (zero P0/P1) / B (allow 1-2 P1) / C (allow more)"
- `auto_fix` — "Should the review stage auto-apply suggested fixes? [Y/n]"
- `max_review_rounds` — "Max review iterations: 1 / 2 / 3 (default 3)"
- `domains` — "Domain standards packs (e.g. python, tauri, react)? Enter comma-separated names or leave empty"
- `recommended_model` — "Preferred Claude model: opus / sonnet / haiku"
- `mechanical_checks` — "Pre-review shell commands (lint, type-check): e.g. `uv run ruff check .`, `uv run mypy .`"
- Reviewers to enable beyond preset defaults — power user option, show as optional

**Risk:** Medium. Rewrites `/harness-maker:make` command template. Regression risk: the non-TTY fallback must stay for when the command is invoked via `!` shell prefix (not from Claude Code's slash UI). Test matrix: (1) slash command from CC, (2) `! harness-maker make` shell, (3) first install on fresh project.

---

### GAP 3 — No pre-install preview (dry-run)

**Current behavior:** Running `harness-maker make` immediately starts the interview and renders files. No "here's what will be written — confirm?" step.

**Evidence (code):** `cli.py` does `reconcile()` → `render()` with no preview gate. `reconcile()` returns conflicts (KEEP/REPLACE decisions) but they're acted on immediately without user confirmation.

**What "preview" should show:**
```
Will install:
  NEW  .claude/agents/code-reviewer.md
  NEW  .claude/skills/autoloop-driver/SKILL.md
  ...18 more files...
KEEP .claude/CLAUDE.md (user-modified — block-merge markers detected)
MERGE .claude/memory/wiki.md (3 user blocks preserved)
REPLACE .claude/hooks/hooks.json (no user modifications)

Proceed? [Y/n]
```

**Implementation options:**

| Option | Approach | Trade-off |
|--------|----------|-----------|
| A | `--dry-run` CLI flag that prints manifest and exits | Zero risk; works from shell |
| B | Preview in slash command via Claude prose (read blueprint, describe it) | No CLI change needed; less precise |
| C | `AskUserQuestion` after interview, before `render()` | Requires threading the preview through CC's AskUserQuestion |

**Recommendation:** Option A (`--dry-run` flag) + Option C (surface it in the slash command template: after interview, show a prose summary of what will happen, then `AskUserQuestion` "Proceed?"). Option B is imprecise — Claude describing the blueprint is not the same as showing the actual file list.

**Risk:** Low for Option A (additive). Medium for combining with AskUserQuestion (need to read blueprint before rendering).

---

### GAP 4 — Post-install summary is minimal

**Current behavior:** `_emit_reconcile_report()` emits something like "3 files kept, 2 blocks merged." That's it. The user doesn't know what was installed, what slash commands are available, what reviewers are enabled.

**What a good post-install summary should contain:**
```
✅ harness-maker 0.7.3 installed to .claude/

Slash commands available:
  /hm:exec-rev-wrap    (execute → review → wrapup)
  /hm:research
  /hm:plan
  ... 8 more commands

Reviewers active: code-reviewer, security-reviewer
Skills active: verify-before-completion, autoloop-driver

Preserved: CLAUDE.md (user-modified), memory/wiki.md
Merged: 2 files with user-authored block-marker content

Next: run /hm:exec-rev-wrap <task> to start your first workflow
      run /hm:configure to change settings without full re-interview
      run /hm:refresh to check for anti-rot updates
```

**Implementation:** `cli.py` already has access to the Blueprint and InterviewAnswers at render time. Add `_emit_install_summary(answers, blueprint, merge_reports)` after the existing `_emit_reconcile_report` call.

**Risk:** Low. Additive to existing CLI output. No rendering changes.

---

### GAP 5 — No uninstall command

**Current behavior:** No `harness-maker remove` or `/hm:uninstall` command. To remove the harness a user must manually delete `.claude/` and `.cursor/` (if cursor target was used).

**What a clean uninstall needs to do:**
1. Remove all harness-managed files (those with `generated_by: harness-maker` frontmatter)
2. Leave user-modified files in place (those with `content_hash` mismatch or `@hm:user:*` blocks)
3. Remove `.cursor/rules/`, `.cursor/commands/hm-*.md`, `.cursor/mcp.json` if cursor target was installed
4. Remove `harness.yaml` last (or ask to preserve answers for future re-install)
5. Print summary of what was removed vs preserved

**Implementation options:**

| Option | Approach | Trade-off |
|--------|----------|-----------|
| A | `harness-maker remove` CLI command | Clean, testable; requires new command |
| B | `/hm:uninstall` generated command | Accessible from CC; calls `harness-maker remove` |
| C | Manual instructions in README only | No code; fragile, error-prone |

**Recommendation:** Option A + B. The fingerprint infrastructure (frontmatter `content_hash` + `generated_by`) already exists — uninstall just needs to read that to identify managed files.

**Risk:** Medium. Need careful handling of files that are "ours" vs "user's". One wrong delete loses user work.

---

### GAP 6 — No `/hm:configure` command for post-install reconfiguration

**User expectation:** After initial install, a user should be able to change one setting (e.g., switch from grade_threshold A to B, or enable the security-reviewer) without re-running the full interview.

**Current workaround:** Edit `harness.yaml` directly, then run `harness-maker make --update`. This requires knowing the yaml schema and remembering to re-render.

**Proposed `/hm:configure` flow:**
```
What would you like to change?
  [preset] Current: Production → change to Side
  [reviewers] Currently: code-reviewer, security-reviewer → toggle others
  [grade_threshold] Currently: A → change to B or C
  [dev_mode] Currently: spec-driven → task-driven
  [workflows] Add/remove workflows
  [targets] Currently: claude-code → add cursor
  [domains] Add/remove domain packs
  [other] Edit harness.yaml directly
```
After selection → Claude updates harness.yaml fields → runs `harness-maker make --update`.

**Risk:** Low. This is a slash command that uses AskUserQuestion → targeted yaml edit → CLI re-render. No new Python code if the slash command calls the existing CLI with flag overrides.

---

## ⚠️ Pitfalls

1. **Dry-run vs actual install state divergence:** If preview reads the blueprint but the actual install reconciles differently (e.g., because a block-merge decision changes between preview and install), the preview is misleading. Solution: dry-run must call `reconcile()` with the same inputs as the real install and display the reconcile decisions.

2. **AskUserQuestion in non-interactive contexts:** If a user runs `/harness-maker:make` via the `!` shell prefix (not as a Claude Code slash command), `AskUserQuestion` won't fire — Claude is not in the loop. The non-TTY fallback to autoloop defaults must remain as the safety net.

3. **Flag explosion:** Adding `--grade-threshold`, `--auto-fix`, `--max-review-rounds`, `--domains`, `--recommended-model`, `--mechanical-checks` adds 6 new CLI flags. The `_apply_dimension_overrides` function needs extending. Testability: each flag needs a unit test. Risk: manageable but not trivial.

4. **Uninstall + block-merge:** Files with `@hm:user:*` blocks have user content mixed with harness content. Uninstalling a "managed" file that has user blocks would lose user content. The uninstaller must detect this and either (a) offer to extract user blocks to a separate file or (b) mark the file as "user-owned" and leave it.

5. **Post-install summary accuracy:** The summary lists "reviewers active" from `InterviewAnswers.reviewers.enabled`. But in the Production preset, the list is the preset default — the user may have overridden some reviewers during the interview. The summary should read from the actual rendered `harness.yaml` after render, not from the in-memory answers, to ensure accuracy.

6. **SessionStart drift hook message is already broken in production:** Any user who has 0.7.3 installed and gets the drift notification is told to run `/hm:make --update` — which doesn't exist. This is a P0 regression fix (the gap has been live since the hook was added).

---

## ❓ Open Questions for `/hm:plan`

1. **Interview order for extended configs:** What's the right AskUserQuestion grouping? Current 8-question flow is already long. Should extended configs (grade_threshold, domains, etc.) be a "Quick setup / Full setup" split, or always shown with smart defaults?

2. **`/hm:configure` scope:** Should it be a single multi-select AskUserQuestion ("what do you want to change?") or a structured REPL-style "change one thing at a time"? The REPL approach is more powerful but harder to implement as a slash command.

3. **Dry-run format:** Should the preview be a table (file-by-file) or a prose summary ("N new files, M files preserved, K blocks merged")? Table is more precise but verbose for large harnesses.

4. **Uninstall: preserve harness.yaml?** After removing all managed files, should `harness.yaml` be kept (so a future re-install can reuse answers without re-interview) or also removed? Suggest: keep by default with an "also remove harness.yaml? [y/N]" prompt.

5. **`/hm:make` generated command scope:** Should `/hm:make` do the full interview (redirecting to the plugin-level interview experience) or just the silent re-render (`--update`)? Recommend: two sub-commands: `/hm:make` = silent re-render, `/hm:make --reinterview` = full interview (routes to `/harness-maker:make`).

6. **CLI flag priority for extended interview answers:** When `--grade-threshold=B` is passed, does it override the `harness.yaml` value or merge with it? The existing `_apply_dimension_overrides` pattern suggests: CLI flag wins over harness.yaml, which wins over preset default.

---

## 📚 Sources

All findings are from direct codebase analysis (no external URLs). Key files examined:
- `src/harness_maker/hooks/sessionstart_drift.py` — broken update notification
- `src/harness_maker/interview.py` — current interview flow, 8 questions
- `src/harness_maker/cli.py` — make command, non-TTY detection, `_apply_dimension_overrides`
- `src/harness_maker/models.py` — `InterviewAnswers`, `HarnessConfig` — full field set
- `src/harness_maker/templates/hooks/hooks.json.j2` — SessionStart hook wiring
- `.claude/commands/hm/` — installed slash commands (no `make.md` present)
- Developer tool installation UX patterns: Homebrew, VS Code extension activation, Oh-My-Zsh, GitHub CLI auth flow (inferred best practices, not cited)

---

## 🔗 Related Internal Docs

- [[RESEARCH-harness-gap-cot-2026-05]] — prior research on harness content gaps
- [[PLAN-plugin-vs-generator-2026-05]] — generator architecture rationale (why we pre-render, not runtime)
- [[RESEARCH-loop-interview-intensity]] — interview intensity tradeoffs for autoloop

---

## Priority Stack (inferred urgency)

| Priority | Gap | Why |
|----------|-----|-----|
| P0 — Fix now | GAP 1: broken update notification | Deployed to all users; `/hm:make` doesn't exist |
| P1 — Next sprint | GAP 2: AskUserQuestion interview | Core value prop is the interview; currently silent |
| P1 — Next sprint | GAP 6: `/hm:configure` command | Reduces friction for post-install changes |
| P2 — Soon | GAP 4: post-install summary | Delight moment; also validates install |
| P2 — Soon | GAP 3: dry-run preview | Safety; important for brownfield users |
| P3 — Later | GAP 5: uninstall command | Needed for completeness; lower urgency |
