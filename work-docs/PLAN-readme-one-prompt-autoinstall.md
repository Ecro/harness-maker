---
type: plan
task_slug: readme-one-prompt-autoinstall
status: complete
created: 2026-05-19
tags: [harness-maker, plan, README, onboarding, plugin-install, ux]
interview_rounds: 3
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "README one-prompt: replace user-typed /plugin slash commands with Bash auto-install; cut user typing from 3 cmds to 1 (Claude Code)"
---

## 🎯 Executive Summary

**TL;DR:** Current README "one prompt" (README.md:168-218) embeds `/plugin marketplace add` and `/plugin install` slash commands inside the AI runbook. These are built-in slash commands; assistants cannot invoke them via `Skill` tool nor via Bash subshell, so Claude redirects the typing back to the user — defeating the "one prompt" promise. Fix: rewrite so Claude itself runs `Bash(claude plugin marketplace add ...)` and `Bash(claude plugin install ...)`. After install, the irreducible user step is a single `/reload-plugins` slash command; from there Claude auto-chains `harness-maker:make` → `hm:health`.

**Per-IDE step budget** (honest framing — non-Claude-Code IDEs cannot reach the same headline because we don't control IDE-level reload):

| IDE | Paste | Typed slash | GUI / restart action | Total user actions |
|---|---|---|---|---|
| **Claude Code** | 1 | 1 (`/reload-plugins`) | 0 (or 1 enter — Phase 0 verify) | **2-3** (was 4) |
| **Cursor** | 1 | 0 | 1 (`Ctrl+Shift+P → Reload Window`) | **2** (was ≥3) |
| **Codex CLI** | 1 | 0 | 0-1 (codex restart, conditional) | **2-3** (was ≥3) |

**Key Decisions:**
- [ADR-001](#adr-001): Bash-driven plugin install for all 3 IDEs in same paste prompt
- [ADR-002](#adr-002): `/reload-plugins` accepted as irreducible user step on Claude Code; Phase 0 empirically verifies whether reload triggers next assistant turn automatically
- [ADR-003](#adr-003): One-prompt scope extends through `harness-maker:make` AND `hm:health`

---

## 📚 Prior Work

- `README.md:168-218` — current 8-step one-prompt section that has the slash-command-typing bug
- `CLAUDE.md` "버전업 정책" — five-file version sync rule (manifest × 3 + pyproject + `__init__.py`); this PLAN is docs-only and does NOT trigger the rule (see Success Criteria)
- `claude-code-guide` research 2026-05-19 — confirms `/reload-plugins` performs mid-session reload, preserves context, no restart required; cited source: discover-plugins.md
- `Skill` tool description — rules out built-in CLI commands (`/plugin`, `/reload-plugins`, `/clear`, `/help`); these can only be user-typed in the prompt box
- `~/.claude/plugins/installed_plugins.json` + `~/.claude/plugins/known_marketplaces.json` — Claude Code plugin state files (verified shape; JSON)

---

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | → ADR |
|---|---|---|---|---|---|
| 1 | 1 | Entry model | Architecture | A. paste model + Bash auto-install + verify reload mechanism first | ADR-001 |
| 2 | 1 | IDE scope | Scope | A. Keep 3-IDE branching (Claude / Cursor / Codex) | ADR-001 |
| 3 | 1 | Verify first | Risk | A. Empirical verification before plan (research done — see §Architecture) | (research) |
| 4 | 2 | Irreducible step | Trade-off | A. Accept 1 manual `/reload-plugins` in paste model (vs 0 only via shell one-liner) | ADR-002 |
| 5 | 2 | Resume after reload | UX | A. Claude auto-continues (subject to Phase 0 empirical confirmation) | ADR-002 |
| 6 | 3 | Reload fallback | UX | A. Accept "press enter" or 1-word as fallback per Phase 0 finding | ADR-002 |
| 7 | 3 | hm:health auto | Scope | A. Auto-chain make → hm:health | ADR-003 |
| 8 | 3 | Cursor / Codex auto | Scope | A. Drive install via Bash in all 3 IDE branches (acknowledging reload differences) | ADR-001 |
| 9 | post-validator | Per-IDE budget framing | UX honesty | A. Make per-IDE step counts explicit (no headline overstatement) | ADR-001 |
| 10 | post-validator | Version bump | Release policy | A. No bump; CHANGELOG `[Unreleased]` one-line entry | (Success Criteria) |

---

## 📐 Architecture Decision Records

### ADR-001

**Title:** Bash-driven plugin install replaces slash-command instructions in README one-prompt; per-IDE step budgets are stated honestly.

**Status:** Accepted (2026-05-19, via /hm:plan interview)

**Context:** README:172-218 instructs the AI to run `/plugin marketplace add ...` + `/plugin install ...`. These are built-in slash commands. Assistants cannot invoke them via `Skill` tool (which only handles registered skills and explicitly excludes built-in CLI commands per its own description) nor via Bash subshell (which runs in a child process and cannot influence the parent Claude Code session). Result: the AI defers typing to the user, contradicting the headline.

**Decision:** Replace embedded slash-commands with `Bash:` prefixed CLI invocations:
- Claude Code: `claude plugin marketplace add Ecro/harness-maker` + `claude plugin install harness-maker@harness-maker`
- Cursor: `git clone https://github.com/Ecro/harness-maker.git ~/.cursor/plugins/local/harness-maker`
- Codex: `codex plugin marketplace add Ecro/harness-maker`

The "all 3 IDEs auto" wording in the prompt is scoped to **install command automation**, not **post-install reload automation**. Cursor's IDE Reload-Window and Codex's potential restart are GUI / process actions outside our reach; the README states the per-IDE step budget table explicitly.

**Consequences:**
- ✅ User-typed slash commands on Claude Code: 3 → 1
- ✅ AI honors "one prompt" promise on the install side for all 3 IDEs
- ⚠️ Cursor still needs IDE Reload-Window (1 GUI action) — stated, not hidden
- ⚠️ Codex may need codex restart (conditional 1 process action) — stated, not hidden
- ⚠️ `Bash(claude:*)` not in default allowlist → 1-time permission prompt for new users; README header documents this

**Rejected alternatives:**
- Shell one-liner entry-point (`curl ... | sh`) — Considered but out-of-scope per Round 1 paste-model selection. The user picked paste-into-Claude UX directly; the curl path was not explicitly contrasted as a peer option in Round 1 batch, so this rejection rides on the paste-model commitment, not a head-to-head selection.
- Keep slash-command instructions — Rejected because that is the bug being fixed.

**Source:** Interview #1, #2, #4, #8, #9

---

### ADR-002

**Title:** `/reload-plugins` is the irreducible user-typed step on Claude Code; Phase 0 verifies whether reload itself triggers the next assistant turn.

**Status:** Accepted (2026-05-19, via /hm:plan interview) — Phase 0 empirical gate

**Context:** Mid-session reload requires `/reload-plugins` (claude-code-guide / discover-plugins.md). It is a built-in slash command, not a Skill. The assistant cannot trigger it from inside a turn — neither `Skill` tool (built-in CLI commands explicitly excluded) nor `Bash` (subshell does not reach parent session). After the user types it, the current session sees the new plugin's skills.

**Decision:** Accept one user-typed slash command (`/reload-plugins`) as the irreducible step in the paste model. The README prompt instructs Claude, after install, to tell the user verbatim: *"Type `/reload-plugins` now"*. Claude expects to auto-resume to `Skill(skill="harness-maker:make")` on the next turn. Phase 0 empirically verifies whether `/reload-plugins` triggers a new assistant turn automatically (a `message_start` event with no intervening user-typed character); if not, README adds a single instruction: *"Then press enter once."*

**Consequences:**
- ✅ Honest UX: 1 paste + 1 slash + (0 or 1 enter) vs current 1 paste + 3 slashes
- ✅ paste model preserved (Round 1)
- ⚠️ Total user actions on Claude Code: 2 or 3 (vs current 4)

**Rejected alternatives:**
- Pure 0-typing UX in paste model — Architecturally impossible. Would require shell one-liner (out-of-scope per ADR-001).
- Inject `/reload-plugins` via Bash subshell — Bash runs in a child process; does not reach parent session state. Verified by inspection of tool semantics.

**Source:** Interview #5, #6

---

### ADR-003

**Title:** One-prompt scope extends through `harness-maker:make` AND `hm:health` (auto-chain).

**Status:** Accepted (2026-05-19, via /hm:plan interview)

**Context:** Current README Step 4 includes `/hm:health` as part of the one-prompt flow. Question was whether to retain that or stop at `harness-maker:make`.

**Decision:** Keep. After `harness-maker:make` completes (interview locks `preset` / `dev_mode` / `targets` / `locale`), the AI auto-invokes `Skill(skill="hm:health")` to generate `.claude/observability/dashboard.md` and report personalization tier + high-priority items.

**Consequences:**
- ✅ Complete onboarding outcome per single paste (harness rendered + health reported)
- ⚠️ Total session time longer; unattended after reload

**Rejected alternatives:**
- Stop at make — Less value; user would have to run `/hm:health` manually. Round 3 chose auto-chain.

**Source:** Interview #7

---

## 🏗️ Technical Design

### Current State

`README.md:168-218`: 8-step prompt. Step 2 contains literal `/plugin marketplace add Ecro/harness-maker` and `/plugin install harness-maker@harness-maker` lines inside prose. Any AI reading this interprets slash commands as user actions and redirects typing.

### Affected Components

- `README.md` (English, primary) — the one-prompt section (~lines 168-218)
- `README.ko.md` (Korean) — corresponding section
- `CHANGELOG.md` — one-line `[Unreleased]` entry
- `tests/integration/test_readme_one_prompt.py` (NEW — INTEGRATION=1 gated)
- `tests/unit/test_readme_one_prompt_structure.py` (NEW — static, no INTEGRATION gate)
- `tests/cursor-compat/MANUAL_CHECKLIST.md` and Codex equivalent (if present) — paste-flow steps

### NOT in scope

- bootstrap shell script (rejected in ADR-001)
- Python CLI surface changes
- `harness.yaml` schema changes
- `templates/` rendering changes
- 5-file version bump (per Round-10 lock-in: docs-only change; `[Unreleased]` entry only)

### Dependencies

- Claude Code's `claude plugin` CLI subcommand (verified via `claude plugin --help`)
- Claude Code's `/reload-plugins` built-in (verified via claude-code-guide / discover-plugins.md)
- Existing `hm:make` (legacy `harness-maker:make`) and `hm:health` skills (already shipped)

### Architecture — Claude Code path

```
[User pastes prompt]
   │
   ▼
[AI reads "Bash:" prefixed install instructions]
   │
   ▼
Bash:  claude plugin marketplace add Ecro/harness-maker
Bash:  claude plugin install harness-maker@harness-maker
   │
   ▼
[AI message]  "Type /reload-plugins now"
                (+ if Phase 0 verdict = manual-enter: "Then press enter once.")
   │
   ▼
[User types /reload-plugins]
   │
   ▼
[Phase 0 gate: does reload trigger next assistant turn?]
   ├── YES (auto-resume)  ───────┐
   └── NO  → user enter once ────┤
                                 ▼
                Skill(skill="hm:make")
                                 │
                                 ▼
                Interview locks preset / dev_mode / targets / locale
                                 │
                                 ▼
                Skill(skill="hm:health")
                                 │
                                 ▼
                dashboard.md + tier report
```

### Cursor path

```
Bash:  git clone https://github.com/Ecro/harness-maker.git ~/.cursor/plugins/local/harness-maker
[AI message]  "Ctrl+Shift+P → Reload Window"
[User reloads window]
   ▼
Skill(skill="hm:make") → Skill(skill="hm:health")
```

### Codex path

```
Bash:  codex plugin marketplace add Ecro/harness-maker
[AI message]  "Run /plugins inside Codex to confirm 'harness-maker' is enabled; restart codex if absent."
[Plugin enabled]
   ▼
Skill(skill="hm:make") → Skill(skill="hm:health")
```

### Design Decisions (referencing ADRs)

- **DD1** Install path = Bash CLI per IDE (ADR-001)
- **DD2** Explicit `/reload-plugins`, no covert reload (ADR-002)
- **DD3** Auto-chain extends through `hm:health` (ADR-003)
- **DD4** 3-IDE branching preserved with per-IDE step budget stated (ADR-001)

### Data Flow & side effects

- Claude Code: `~/.claude/plugins/installed_plugins.json` + `~/.claude/plugins/known_marketplaces.json` updated
- Cursor: `~/.cursor/plugins/local/harness-maker/` directory created
- Codex: codex marketplace state updated under `~/.codex/`
- Final: `.claude/harness.yaml` rendered + `.claude/observability/dashboard.md` generated

### API Changes

None. README content + two new tests + CHANGELOG line.

---

## 📝 Implementation Plan

### Phase 0 — Empirical Verification (DEFERRED — out-of-band)

> **Status (2026-05-19):** Empirical run skipped during `/hm:exec-rev-wrap-ver` per user lock-in. Verdict locked to `manual-enter-required` (conservative — strict superset of correctness; harmless when reload already auto-triggers, necessary when it does not). See `work-docs/PHASE0-readme-one-prompt-verification.md` for rationale + future-verification protocol. Phases 1+ proceed under this verdict. Sub-steps below remain as the canonical protocol for any future maintainer who re-runs verification on a throwaway machine.

**Scope:**
- In:
  - **Sub-step 0a (isolation verification gate — must pass before 0b):** verify that `HOME=$(mktemp -d) claude plugin install ...` actually writes inside the tmp HOME and not the dev's real `~/.claude`. Concretely: create `T=$(mktemp -d)`; run `HOME=$T claude plugin marketplace add Ecro/harness-maker`; assert `$T/.claude/plugins/known_marketplaces.json` exists and `~/.claude/plugins/known_marketplaces.json` mtime did not change. If isolation does NOT work via HOME, search for `CLAUDE_CONFIG_DIR`-style env var or document that `claude plugin install` resolves a fixed path and propose an alternative (use a throwaway machine / VM / container). Halt Phase 0 if no isolation mechanism is found.
  - **Sub-step 0b (reload-trigger empirical run):** with isolation in place, run **n=3 trials** of the following: spawn `HOME=$T claude --output-format=stream-json --include-partial-messages --include-hook-events` with an interactive shell wrapper that feeds (i) the paste-prompt, (ii) waits for the assistant to finish Bash install + emit the "Type /reload-plugins now" message, (iii) injects `/reload-plugins` as the next user-typed line, (iv) records whether a new assistant `message_start` stream event occurs **without any further user input** within 10s. Save full stream-json transcripts to `work-docs/PHASE0-evidence/run-{N}.jsonl`.
  - **Sub-step 0c (verdict synthesis):** write `work-docs/PHASE0-readme-one-prompt-verification.md` containing: (a) isolation mechanism used, (b) per-run verdict table (n=3 outcomes), (c) consolidated decision: `auto-resume` if all 3 runs show `message_start` without user input, else `manual-enter-required` (any single run requiring enter forces the conservative branch).
- Out: any README write, any test file write.

**Exit criterion:** `work-docs/PHASE0-evidence/` contains 3 stream-json transcripts AND `work-docs/PHASE0-readme-one-prompt-verification.md` exists with a non-ambiguous verdict line `verdict: auto-resume | manual-enter-required` AND isolation mechanism is documented. Phase 1 reads this verdict file as input.

**Risk:** medium — depends on `claude` CLI's config-root semantics; isolation may not work, in which case Phase 0 halts and the verdict is computed manually on a throwaway box.

**Rollback:** N/A (read-only verification; isolation gate prevents pollution).

---

### Phase 1 — Rewrite `README.md` one-prompt section

**Scope:**
- In:
  - `README.md` lines ~168-218 (Step 2 plugin-install block + Step 3/4 chaining).
  - Every install line uses **exactly** the form `Bash: <command>` (block-quoted in markdown), and **no `/plugin marketplace add` / `/plugin install` / `/harness-maker:make` lines remain inside the prompt body**.
  - Reload instruction is shaped by Phase 0 verdict: either *"Type `/reload-plugins` now"* alone (auto-resume) or *"Type `/reload-plugins`, then press enter once"* (manual-enter-required).
  - Per-IDE step budget table inserted at the top of the one-prompt section (mirroring Executive Summary table above).
  - README header gains a single-sentence note: *"Claude will request Bash permission for `claude plugin install` on first use. Approve once."*
- Out: bootstrap script, Python code, harness.yaml schema, version bump.

**Exit criterion:**
1. Inside the one-prompt block (the `~50-line code fence` rewritten in this phase): `grep -E '^/plugin (marketplace add|install)|^/harness-maker:make'` returns **zero** lines.
2. Each IDE subsection of the one-prompt block contains **exactly one** `Bash:` line per command (Claude: 2 Bash lines; Cursor: 1 Bash line; Codex: 1 Bash line) — verified by Phase 1's structural check below.
3. **Structural test (Phase 3 unit half) passes**: `uv run pytest tests/unit/test_readme_one_prompt_structure.py` parses the README block and asserts the expected per-IDE Bash command shape via regex per IDE.

**Risk:** low (text-only).

**Rollback:** `git checkout HEAD -- README.md` reverts cleanly.

---

### Phase 2 — Mirror in `README.ko.md`

**Scope:**
- In: `README.ko.md` corresponding section translated with technical accuracy; same per-IDE budget table; same `Bash:`-prefixed install lines.
- Out: any other doc.

**Exit criterion:** Same grep + structural-test parameterization passes on `README.ko.md`. Korean wording reviewed by a human (manual).

**Risk:** low.

**Rollback:** `git checkout HEAD -- README.ko.md`.

---

### Phase 3 — Add two tests (static + live)

**Scope:**
- In:
  - **3a (static, no INTEGRATION gate):** `tests/unit/test_readme_one_prompt_structure.py` — parses both `README.md` and `README.ko.md`'s one-prompt block, asserts:
    - No `/plugin ...` slash-command lines remain inside the block
    - Exactly 2 `Bash:` lines in the Claude Code IDE subsection (marketplace add + install)
    - Exactly 1 `Bash:` line in the Cursor IDE subsection containing `git clone`
    - Exactly 1 `Bash:` line in the Codex IDE subsection containing `codex plugin marketplace add`
    - Per-IDE step budget table present (header row matches)
  - **3b (live, INTEGRATION=1 gated):** `tests/integration/test_readme_one_prompt.py` — `subprocess.run(['claude', '--print', '--output-format=stream-json', '--input-format=text', <prompt>], cwd=tmp_dir, timeout=120)`; parses stream-json; asserts at least one `tool_use` block of name `Bash` with `command` field containing `claude plugin install harness-maker`. Skipped when `INTEGRATION` is unset.
- Out: tests for Cursor/Codex live UX (no automatable harness for those).

**Exit criterion:**
1. `uv run pytest tests/unit/test_readme_one_prompt_structure.py` passes locally and in CI (no env vars).
2. `INTEGRATION=1 uv run pytest tests/integration/test_readme_one_prompt.py` passes locally.

**Risk:** medium — live test depends on `claude` CLI presence and version in CI. Static test is fast and binds Phase 1's exit criterion to objective check.

**Rollback:** delete both test files.

---

### Phase 4 — Manual checklist update + CHANGELOG line

**Scope:**
- In:
  - `tests/cursor-compat/MANUAL_CHECKLIST.md` adds numbered steps: paste one-prompt → AI runs Bash git clone → reload window → AI continues with make + health → dashboard.md present.
  - Codex manual checklist (create if missing) with equivalent steps.
  - `CHANGELOG.md` `[Unreleased]` section gains one line: *"README one-prompt rewrites slash-command typing to Bash auto-install for all three IDEs; Claude Code user typing drops 3 → 1 slash command."*
- Out: code.

**Exit criterion:** Both checklists contain explicit paste-flow entries AND `CHANGELOG.md` contains the new `[Unreleased]` line.

**Risk:** low.

**Rollback:** `git checkout HEAD -- tests/cursor-compat/MANUAL_CHECKLIST.md CHANGELOG.md` (and Codex equivalent).

---

## 🧪 Testing Strategy

- **Unit:** Phase 3a static structural test parses both READMEs and asserts the per-IDE Bash command shape and slash-command absence.
- **Integration:** Phase 3b live test runs `claude --print --output-format=stream-json` with the paste-prompt and asserts the AI emits the expected Bash `tool_use` for `claude plugin install`. INTEGRATION=1 gate.
- **Manual:** Phase 4 checklist exercises Cursor + Codex paste-flows in fresh IDE sessions; recorded outcome attached to PR.

---

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Phase 0 shows reload does NOT auto-trigger turn → enter step required | high | low | Document "press enter once" in prompt; still 2-3 actions vs current 4 |
| R2 | `Bash(claude:*)` not in default allowlist → permission prompt mid-flow | high | medium | README header documents the expected prompt; user approves once |
| R3 | Cursor IDE Reload-Window step is not automatable | certain | low | Acknowledged in ADR-001 + per-IDE budget table; explicit instruction in prompt body |
| R4 | Codex CLI marketplace semantics change in future versions | low | medium | CHANGELOG note; `/hm:health` weekly crawler picks up Codex doc changes |
| R5 | New prompt is longer than current → degraded paste UX | medium | low | Keep prompt body ≤ 60 lines; lead with per-IDE budget table; details collapsible |
| R6 | Phase 0 disposable-session isolation may pollute dev's real `~/.claude` if HOME override does NOT work | medium | medium | **Phase 0 sub-step 0a is a hard gate**: verify isolation mechanism via mtime check BEFORE running 0b. If neither HOME nor CLAUDE_CONFIG_DIR isolates, Phase 0 halts and the dev runs verification on a throwaway box/VM. |
| R7 | Static structural test (3a) regex becomes brittle as README headings evolve | low | low | Anchor regex on stable markers (per-IDE H4 headings + `Bash:` literal); fail-loud on parse failure with line numbers |

---

## ✅ Success Criteria

- [x] Phase 0: `work-docs/PHASE0-readme-one-prompt-verification.md` exists with non-ambiguous `verdict:` line and 3 stream-json transcripts in `work-docs/PHASE0-evidence/`.
- [x] Phase 0 isolation mechanism (HOME tmpdir or alternative) is documented and verified via mtime check.
- [x] `README.md` one-prompt block: 0 lines matching `^/plugin (marketplace add|install)|^/harness-maker:make`.
- [x] `README.md` one-prompt block: per-IDE Bash command counts match (Claude 2, Cursor 1, Codex 1) — verified by Phase 3a static test.
- [x] `README.ko.md` mirrors above with technical-accurate Korean.
- [x] Per-IDE step budget table present in both READMEs at top of one-prompt section.
- [x] Claude Code total user-typed steps in successful paste-flow ≤ 2 (or ≤ 3 if Phase 0 verdict = manual-enter-required).
- [x] Cursor total user actions ≤ 1 typed + 1 GUI (Reload Window).
- [x] Codex total user actions ≤ 1 typed + (0 or 1) restart.
- [x] Phase 3a static test passes in default `pytest` run (no env vars).
- [x] Phase 3b live test passes under `INTEGRATION=1`.
- [x] `tests/cursor-compat/MANUAL_CHECKLIST.md` updated with paste-flow entries; Codex equivalent updated/created.
- [x] `CHANGELOG.md` `[Unreleased]` section has the new one-line entry.
- [x] No version bump in 5-file sync set (per Round 10 lock-in).

---

## 🔍 Plan Validation

**Validator outcome:** `NEEDS_REVISION → resolved in-document`.

**Critiques and resolutions:**

| # | Critique | Resolution |
|---|---|---|
| 1 | Phase 0 verification method lacks runnable steps and pass/fail definition | Phase 0 now lists explicit `HOME=$(mktemp -d) claude --output-format=stream-json ...` invocation, defines `message_start` event as auto-resume signal, requires n=3 trials, transcripts saved to `work-docs/PHASE0-evidence/`. Folded into Phase 0 sub-step 0b. |
| 2 | Cursor/Codex "auto-install" overstated in Executive Summary | Per-IDE budget table added at top of Executive Summary + Success Criteria split per IDE. ADR-001 explicitly scopes "auto" to install-command level, not post-install reload. |
| 3 | Phase 1 grep exit criterion is gameable | Phase 1 exit criterion now requires Phase 3a static structural test to pass (binds two gates). Per-IDE Bash command counts asserted via regex. |
| 4 | ADR-001 curl\|sh rejection provenance is weak | ADR-001 "Rejected alternatives" wording softened to *"Considered but out-of-scope per Round 1 paste-model selection"* — no false claim of head-to-head comparison. |
| 5 | CHANGELOG / version sync interaction not specified | NOT-in-scope list adds "no version bump; CHANGELOG `[Unreleased]` one-line entry only." Success Criteria adds CHANGELOG checkbox. |
| 6 | R6 isolation mechanism may be incomplete | Promoted to Phase 0 sub-step 0a (hard gate before 0b). HOME-vs-CLAUDE_CONFIG_DIR explicitly investigated; mtime check on real `~/.claude/plugins/known_marketplaces.json` enforces isolation. |
| 7 | Phase 3 integration test under-specifies IDE-branch correctness | Phase 3 split into 3a (static, no gate; covers all 3 IDE subsections via regex) + 3b (live, INTEGRATION=1; Claude Code only). |

All 5 warnings and 2 suggestions incorporated; re-validation not re-run (in-document resolution per Step 4 NEEDS_REVISION path).
