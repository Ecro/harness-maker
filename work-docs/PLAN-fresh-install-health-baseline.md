---
type: plan
task_slug: fresh-install-health-baseline
status: planning
created: 2026-05-18
tags: [harness-maker, plan, python, readiness, health, templates, side-preset]
interview_rounds: 4
adrs: 6
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Make fresh /hm:make produce a Side/Production harness whose /hm:health reports zero false-positive P0/P1 by fixing 3 template gaps + 1 readiness signal + 2 skill trims."
---

## 🎯 Executive Summary

A fresh `/hm:make` install currently fails its own `/hm:health` immediately with 11 P0/P1 signals. Investigation classifies them into 4 categories:

1. **Intended fresh-install noise** (telemetry files + CI workflow) — accepted, codified as `INTENDED_P0_SIGNALS` allowlist with samples-based auto-release.
2. **Template gaps** (`memory:` key missing from harness.yaml, `permissions.deny` empty in settings.json).
3. **Self-violated thresholds** (Side ≤100/50 lines vs bundled assets — every bundled skill violates, ~5 agent bodies violate).
4. **Unknown-stack cascade** (board-yaml / shell-only projects hit two P0s simultaneously).

Goal: zero false-positive P0/P1 on fresh install. Real verification gaps still surface.

**Key decisions (ADRs):**
- ADR-001: Side preset thresholds raised to agent ≤150, skill ≤100 (was 100/50). Production unchanged.
- ADR-002: `memory:` baseline schema = `{enabled: true, dir: .claude/memory, files: [failures.md, wiki.md]}`.
- ADR-003: Side·Production `permissions.deny` baseline = 4 patterns (rm, curl, Write(/etc, Write(~/.ssh).
- ADR-004: Unknown-stack auto-degrade — `_dim_verification` reduces `stack_detected` + `tests_present` weight when `stacks == set()`. Future-stack degradation risk accepted.
- ADR-005: Migration of existing installs relies on existing `render.py` semantics (`_merge_permissions` list-union + `_preserve_yaml_user_keys` + post-render `content_hash` recompute). No new code path, no `--upgrade` flag.
- ADR-006: Telemetry 2-signal accepted as fresh-install intended noise via `INTENDED_P0_SIGNALS` allowlist. Allowlist applies only while project telemetry samples < 5 (samples-based TTL); beyond 5, normal P0 surfacing returns.

**Impact:** ~6 files touched (4 templates + 1 readiness module + 1 CLAUDE.md), 2 skill SKILL.md trims, 1 new integration test, 1 CI workflow line, release as 0.17.0 (minor — new `memory:` baseline key in shipped harness.yaml). ~6h work.

## 📚 Prior Work

- **0.15.3 release runbook** (CLAUDE.md "릴리스 절차"): 5-file version sync; tag-push-only release pattern; do NOT manually `gh release create`.
- **REVIEW-2026-05-08 (security/permissions)** in CLAUDE.md "보안 / 권한": top-level `permissions.deny` and reviewer/executor agent frontmatter deny are separate concerns; this PLAN only touches top-level baseline.
- **failures.md 2026-05-08** (REVIEW M1, M7): interpreter Bash deny patterns (`python:*`, `node:*`, `sh:*`, `bash:*`) already live in reviewer/executor agent frontmatter; top-level baseline (this PLAN) is the minimal 4-pattern security floor.
- **CLAUDE.md "Context Lint (v1.6)"**: declares thresholds; ADR-001 supersedes the Side row (100/50 → 150/100).
- **ADR-001 (existing CLAUDE.md)**: P0/P1 health items don't auto-apply; this PLAN respects that — Phase 1 changes templates only; existing-install migration is opportunistic via existing render path.

## 🎙️ Interview Transcript

| # | Round | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | 1 | architecture | Side agent/skill thresholds: trim vs raise vs hybrid vs allowlist? | B (raise to 150/100) | ADR-001 |
| 2 | 2 | contract | `memory:` yaml schema depth? | B (useful baseline: enabled + dir + files) | ADR-002 |
| 3 | 2 | contract | `permissions.deny` baseline scope? | A (4-pattern minimum, Side = Production) | ADR-003 |
| 4 | 2 | architecture | Unknown-stack P0 cascade fix? | A (auto-degrade weight) | ADR-004 |
| 5 | 3 | risk | Telemetry hint copy fix? | B (differentiate, keep both signals) | ADR-006 |
| 6 | 3 | risk | Existing-install back-compat policy? | A → pivoted to ADR-005 after validator pass 2 | ADR-005 |
| 7 | 3 | testing | Dogfood CI gate on fresh-install readiness? | A (full integration pytest) | (operational; see Phase 4) |
| 8 | FU1 | architecture | YAML migrate path & content_hash? | A → superseded by ADR-005 | (resolved by ADR-005) |
| 9 | FU1 | architecture | `deny: []` user-intent guard? | A → superseded by ADR-005 | (resolved by ADR-005) |
| 10 | FU1 | architecture | Stack-degrade positive marker? | C (accept broad-degrade risk) | ADR-004 risk note |
| 11 | FU1 | release | Version + user-side rollback shape? | C → superseded by ADR-005 (no `--upgrade` needed) | (resolved by ADR-005) |
| 12 | Val2 | architecture | Phase 4 fate given existing render semantics? | A (drop entirely) | ADR-005 |
| 13 | Val2 | architecture | INTENDED_P0_SIGNALS allowlist TTL? | A (samples<5 auto-release) | ADR-006 |
| 14 | Val2 | test | Idempotency assertion spec? | A (raw bytes equality) | (Phase 4 exit detail) |

Validator passes: 1 (MAJOR_REVISION on Phase 4 reconcile/yaml/stack-gate), 2 (MAJOR_REVISION on Phase 4 redundancy with render.py). After pass 2, the architectural pivot in interview rounds 12-14 superseded ADR-005 (original) and ADR-006 (original). Final outcome: MAJOR_REVISION_RESOLVED via redesign, not accept-as-risk.

## 📐 Architecture Decision Records

### ADR-001: Raise Side preset context-lint thresholds (agent 100→150, skill 50→100)
**Status:** Accepted (2026-05-18, via /hm:plan interview Round 1)
**Context:** All 12 bundled skills and 4-5 bundled agent body templates violate Side ≤100/50 thresholds. Thresholds were aspirational and never enforced at template level. Trimming would force ~half the content out of skills like autoloop-driver (149 body lines).
**Decision:** Raise Side thresholds in `_CONTEXT_LIMITS` to agent ≤150, skill ≤100. Production unchanged at 200/150.
**Side identity replacement:** With prompt-size differentiation gone, Side ≠ Production now lives in: reviewer count (1 vs 5), grade threshold (B vs A), spec_gate (warn vs block), security on_finding.high (warn vs block), worktree.scope ([execute] vs [execute, plan]). Prompt-size axis is informational only.
**Consequences:**
- ✅ Most bundled assets now pass without trimming (5 agent bodies all ≤150).
- ✅ Single small code change (`_CONTEXT_LIMITS` dict + CLAUDE.md "Context Lint" section).
- ⚠️ Two skills still over new 100 limit: autoloop-driver (149 body) and verify-before-completion (~108 body). Phase 3 trims these specifically.
- ⚠️ "Side = lean prompts" semantic is gone — differentiation explicitly relocated.
**Rejected:** A (full diet) — risks substance loss. C (Hybrid) — keeps two policies in flight. D (allowlist exemption) — adds maintenance surface, dilutes lint signal.
**Source:** Interview #1.

### ADR-002: `memory:` baseline schema in harness.yaml
**Status:** Accepted (2026-05-18)
**Context:** `Side.yaml.j2` / `Production.yaml.j2` ship without any `memory:` section, but `readiness.py:707` requires the literal `"memory:"` substring. Result: every fresh install permanently fails `harness_memory_configured` until user manually edits.
**Decision:** Both yaml templates render a 4-line baseline:
```yaml
memory:
  enabled: true
  dir: .claude/memory
  files: [failures.md, wiki.md]
```
Placed before `security:` section.
**Consequences:**
- ✅ Fresh install passes `harness_memory_configured` signal.
- ✅ Declared contract for memory consumers (read `dir` + `files` from config).
- ⚠️ Adds 4 lines to harness.yaml.
**Rejected:** A (one-line stub) — passes check but doesn't declare contract. C (rich with retention/autoload) — premature, no consumers, deprecation risk.
**Source:** Interview #2.

### ADR-003: `permissions.deny` 4-pattern baseline (Side = Production)
**Status:** Accepted (2026-05-18)
**Context:** Both Side and Production `settings.json` templates ship `"deny": []`. Readiness requires 3-of-4 dangerous patterns (`rm`, `curl`, `Write(/etc`, `Write(~/.ssh`). CLAUDE.md reviewer/executor agent frontmatter has richer deny lists, but those are agent-scope, not project-scope.
**Decision:** Both Side and Production settings.json render:
```json
"deny": ["Bash(rm:*)", "Bash(curl * | sh)", "Write(/etc/**)", "Write(~/.ssh/**)"]
```
**Consequences:**
- ✅ Fresh install passes both `permissions_deny_present` and `deny_covers_dangerous` signals.
- ✅ Project-level safety floor active in both presets.
- ⚠️ Security differentiation between Side and Production lives elsewhere (reviewer count, grade, spec_gate per ADR-001).
**Rejected:** B (CLAUDE.md-aligned ~8 pattern) — over-engineering Side. C (graduated Side/Production split) — splits maintenance.
**Source:** Interview #3.

### ADR-004: Unknown-stack auto-degrade in `_dim_verification`
**Status:** Accepted (2026-05-18)
**Context:** Projects without a recognized manifest hit `_detect_stacks() == set()`. This cascades into two P0 signals (`stack_detected` weight 20, `tests_present` weight 30). No user-facing knob.
**Decision:** When `stacks == set()`, both signals' weights drop to 5/10 (advisory) and evidence reads "No language stack detected (non-standard project)". Action hint changes to "If non-standard project, this is expected. Otherwise add pyproject.toml/etc."
**Risk note (accepted):** The weight-drop applies to any project where `_detect_stacks() == set()` — including future stacks (Zig, Gleam, …) that `_STACK_TESTERS` doesn't yet register. Accepted risk: when a new stack becomes prevalent, register it in `_STACK_TESTERS` to re-engage the signal. Any future-stack escalation issue should cite this ADR.
**Consequences:**
- ✅ Board-yaml/shell/Makefile-only projects no longer get 2 P0s for project shape.
- ✅ No user config required.
- ⚠️ Real Python projects without pyproject.toml are silently downgraded (edge case).
- ⚠️ Future stacks silently downgraded until `_STACK_TESTERS` learns them.
**Rejected:** A (positive marker gate — too much logic for niche case). B (hybrid weight reduce P0→P2 advisory + always-on warning).
**Source:** Interview #4 + FU-3.

### ADR-005: Migration of existing installs relies on existing `render.py` semantics
**Status:** Accepted (2026-05-18, via plan-validator pass 2 architectural pivot)
**Context:** Original ADR-005 (now superseded) proposed a `--upgrade` flag + KNOWN_SHIPPED_HASHES table + content_hash recompute path for existing-install migration. Plan-validator pass 2 found this duplicates code already in `render.py`:
- `_merge_permissions` (render.py:180-209) deep-merges `permissions.allow/deny/ask` as list union — Phase 1's template change (adding 4 deny entries) automatically unions into existing users' settings.json on next render. No flag needed.
- `_preserve_yaml_user_keys` (render.py:620-682) preserves top-level YAML keys not in template. When template gains `memory:`, existing users without it receive it; users who customized it keep their version (template-wins on top-level overlap per the existing docstring).
- `content_hash` recompute already runs post-preservation at render.py:602-603.
**Decision:** No new migration code path. Phase 1 (template additions) + existing render semantics deliver migration automatically on existing users' next `/hm:make`. Phase 4 verifies this with integration tests but adds zero production code beyond Phase 1's templates.
**Consequences:**
- ✅ Phases drop from 7 → 6; maintenance surface drops significantly.
- ✅ No `--upgrade` flag to teach users.
- ✅ No KNOWN_SHIPPED_HASHES table to maintain across releases.
- ✅ Idempotent by construction (existing render path already converges).
- ⚠️ A user who deliberately set `deny: []` (empty) silently gains the 4 baseline patterns on next render. Considered acceptable because (a) the 4 patterns are minimal security baseline (rm-rf, curl|sh, /etc, ~/.ssh) and (b) `_merge_permissions` union semantics are pre-existing and documented; this PLAN does not change them.
- ⚠️ A future change wanting "replace stale baseline deny patterns" (i.e., subtraction) needs its own ADR — this one only covers additive baseline injection via union.
**Rejected:**
- A (original) `--upgrade` flag + KNOWN_SHIPPED_HASHES + content_hash recompute — duplicates `_merge_permissions` + `_preserve_yaml_user_keys` + render.py:602-603. Rejected by plan-validator pass 2.
- B (test-only verification but keep flag) — half-measure; ships a flag that's redundant.
- C (keep flag despite redundancy) — adds command-surface for no benefit.
**Source:** Interview #6 + FU1-Q1/Q2 + Val2-Q1.

### ADR-006: Telemetry intended-noise allowlist with samples-based TTL
**Status:** Accepted (2026-05-18)
**Context:** `_dim_observability_setup` has two signals (`metrics_jsonl_present` weight 25, `metrics_has_samples` weight 25) that both fail on fresh install — the metrics file is not created until the first PostToolUse hook fires. The hint on `metrics_jsonl_present` says "Install the PostToolUse telemetry hook (run /hm:make)", misleading immediately after `/hm:make`.
**Decision:** Two parts:
1. Hint copy: `metrics_jsonl_present` hint changes to "First Claude Code tool use will create this file (PostToolUse hook is installed)."
2. Allowlist with TTL: `INTENDED_P0_SIGNALS = {"metrics_jsonl_present", "metrics_has_samples", "ci_workflow_present"}` codifies the fresh-install noise set. Phase 4's integration test asserts P0 ⊆ INTENDED_P0_SIGNALS only when telemetry samples < 5. Once samples ≥ 5, normal P0 surfacing applies — readiness emits these P0s without suppression, exposing real hook regressions (e.g., hook misconfigured and stopped firing).
**Consequences:**
- ✅ Fresh-install dashboard surfaces these P0s with clearer language; gate passes.
- ✅ Beyond samples=5, the allowlist deactivates — long-running projects regain normal P0 surfacing for telemetry signals (no permanent blind spot).
- ⚠️ Allowlist still grows when new "intended noise" categories appear; each addition needs an ADR amendment.
**Rejected:** Permanent grow-only allowlist (blind-spot risk). Collapsing the two signals (user Round 3 rejected). Removing `metrics_has_samples` entirely (drops dim weight allocation).
**Source:** Interview #5 + Val2-Q2.

## 🏗️ Technical Design

### Current State (verified file:line)
- `templates/harness-yaml/Side.yaml.j2:1-91` and `Production.yaml.j2:1-91` — identical except `worktree.scope` (line 84) and `security.*` (lines 88, 91). Neither has `memory:` section.
- `templates/settings/Side.json.j2:2` — `"deny": []`.
- `templates/settings/Production.json.j2` — same empty deny.
- `readiness.py:47-55` — `_CONTEXT_LIMITS` Side agent 100, skill 50.
- `readiness.py:57-63` — `_DANGEROUS_DENY_PATTERNS` (4 entries).
- `readiness.py:496-578` — `_dim_verification`, no unknown-stack branch.
- `readiness.py:723-788` — `_dim_observability_setup` has 4 signals; two telemetry signals both fail on fresh install.
- `readiness.py:707` — `"memory:" in _read_text(harness)` substring check.
- `render.py:180-209` — `_merge_permissions` list-union semantics already shipped.
- `render.py:620-682` — `_preserve_yaml_user_keys` already preserves user-added top-level keys.
- `render.py:602-603` — content_hash recompute already runs post-preservation.

### Affected Components
1. **Templates**: harness-yaml/{Side,Production}.yaml.j2, settings/{Side,Production}.json.j2.
2. **Readiness scoring**: `readiness.py` `_CONTEXT_LIMITS` + `_dim_verification` unknown-stack branch + `_dim_observability_setup` hint copy + samples-based allowlist gate.
3. **Skills bundled** (over new 100 limit): autoloop-driver (149 body → ≤100), verify-before-completion (~108 body → ≤100).
4. **CLAUDE.md**: "Context Lint (v1.6)" thresholds row update.
5. **Tests**: new `tests/integration/test_fresh_install_readiness.py`.
6. **CI workflow**: add new integration test to quality-gate job.

### Out of scope (explicit)
- Cursor `.cursor/` and Codex `.codex/` permission equivalents — tracked separately. Users with `targets: [cursor]` or `targets: [codex]` still get the `.claude/settings.json` benefit at minimum because both IDEs read `.claude/` natively.
- Reviewer/executor agent frontmatter `permissions.deny` lists — agent-scope, not touched by this PLAN.
- Memory autoload/retention features — ADR-002 declares baseline only; consumer work is separate.

### Data Flow
`/hm:make` → synthesize.py → reconcile/render — `render.py._merge_permissions` unions new template denies into existing settings.json; `render.py._preserve_yaml_user_keys` preserves user top-level keys when template adds new ones; `render.py:602-603` recomputes content_hash → atomic write → user runs `/hm:health` → `readiness.py` reads files → emits signals (now with raised limits, unknown-stack degrade, samples-based telemetry allowlist).

### API/Schema Changes
- `harness.yaml`: new top-level `memory:` block (additive, preserved by `_preserve_yaml_user_keys` semantics).
- `settings.json`: 4 new `permissions.deny` entries (additive via `_merge_permissions` union).
- `_CONTEXT_LIMITS`: 4 dict-values changed (Side rows only).
- `_dim_verification`: behavior change on `stacks == set()` path.
- `_dim_observability_setup`: hint copy + new samples-based allowlist gate.

## 📝 Implementation Plan

**Phase 1 — Template additions (memory + deny)**
- **Scope (in):** `templates/harness-yaml/Side.yaml.j2`, `templates/harness-yaml/Production.yaml.j2`, `templates/settings/Side.json.j2`, `templates/settings/Production.json.j2`.
- **Scope (out):** No Python code changes.
- **Exit criterion:** `uv run python -m harness_maker.cli make /tmp/hm-test-side --preset Side --locale en` followed by `grep "^memory:" /tmp/hm-test-side/.claude/harness.yaml` returns the block, AND `python -c "import json; print(json.load(open('/tmp/hm-test-side/.claude/settings.json'))['permissions']['deny'])"` returns a list with 4 elements containing `rm`, `curl`, `/etc`, `/.ssh` substrings. Same for `--preset Production`.
- **Risk:** low (template-only).
- **Rollback:** revert this phase's 4 files.

**Phase 2 — readiness.py: thresholds + auto-degrade + hint copy + allowlist gate**
- **Scope (in):** `src/harness_maker/readiness.py`.
- **Scope (out):** templates, tests.
- **Changes:**
  - `_CONTEXT_LIMITS`: Side agent 100→150, Side skill 50→100. Production unchanged.
  - `_dim_verification`: add `stacks == set()` branch — `stack_detected` weight 20→5, `tests_present` weight 30→10, evidence and action softened.
  - `_dim_observability_setup`: `metrics_jsonl_present` hint changes to "First Claude Code tool use will create this file (PostToolUse hook is installed)."
  - New module-level constant `INTENDED_P0_SIGNALS = {"metrics_jsonl_present", "metrics_has_samples", "ci_workflow_present"}` (used by Phase 4 test only; readiness scoring itself unchanged in this regard).
- **Exit criterion:** `uv run pytest tests/unit/test_readiness.py -x` passes after updating any tests with hardcoded old limits or old hint strings.
- **Risk:** medium (changes scoring math + snapshot test updates likely).
- **Rollback:** revert `readiness.py`; Phase 1 stands.

**Phase 3 — CLAUDE.md sync + skill trims + agent-side verification**
- **Scope (in):** `CLAUDE.md` ("Context Lint (v1.6)" section), `templates/skills/autoloop-driver/SKILL.md.j2`, `templates/skills/verify-before-completion/SKILL.md.j2`.
- **Scope (out):** other skills (already ≤100 under new limit), agent body templates (already ≤150 under new limit — verified at draft time).
- **CLAUDE.md change:** Update thresholds row to "agent ≤ Side 150 / Production 200, skill ≤ Side 100 / Production 150".
- **autoloop-driver trim plan:** remove "Dev-time Python API" reference block + "Reference" block at bottom (lines ~136-149); condense "4-Gate Convergence" prose; target ≤100 body lines (current 149).
- **verify-before-completion trim plan:** remove duplicate "Why" paragraphs; target ≤100 body lines (current ~108).
- **Exit criterion:** 
  ```bash
  for f in src/harness_maker/templates/skills/*/SKILL.md.j2; do
    body=$(awk 'BEGIN{fm=0} /^---$/{fm++; next} fm>=2{print}' "$f" | wc -l)
    [ "$body" -gt 100 ] && echo "OVER $f $body" && exit 1
  done
  for f in src/harness_maker/templates/agents/*_body.md.j2; do
    body=$(awk 'BEGIN{fm=0} /^---$/{fm++; next} fm>=2{print}' "$f" | wc -l)
    [ "$body" -gt 150 ] && echo "OVER $f $body" && exit 1
  done
  echo "OK"
  ```
  prints `OK`.
- **Risk:** low (trim removes reference/internal blocks; user-facing how-to retained — audit each removed block).
- **Rollback:** revert these files; Phases 1-2 stand.

**Phase 4 — Integration test for fresh install + existing-install migration + idempotency**
- **Scope (in):** new file `tests/integration/test_fresh_install_readiness.py`. Per `pytest.mark.skipif(not os.getenv("INTEGRATION"))` guard per CLAUDE.md test policy.
- **Scope (out):** no production code changes (per ADR-005).
- **Test cases:**
  1. **Fresh Side**: render Side into tmpdir via `cli.make`; run `readiness.compute(tmpdir)`; assert `failing_p0_ids ⊆ INTENDED_P0_SIGNALS`; assert `composite_score >= 0.70`.
  2. **Fresh Production**: same as 1, with Production; `composite_score >= 0.75`.
  3. **Existing-install migration (harness.yaml)**: create tmpdir with a pre-existing `.claude/harness.yaml` lacking `memory:` key (simulate 0.16.0 install); run `cli.make`; assert `memory:` is now present in rendered file (delivered by `_preserve_yaml_user_keys` semantics, no new code).
  4. **Existing-install migration (settings.json)**: create tmpdir with pre-existing `.claude/settings.json` having `"deny": []`; run `cli.make`; assert deny array now contains 4 baseline patterns (delivered by `_merge_permissions` union, no new code).
  5. **Idempotency**: run `cli.make` twice in the SAME tmpdir. Assert `Path(tmpdir / ".claude" / "harness.yaml").read_bytes()` is identical between runs. Same for settings.json. Catches `generated_at` timestamp drift AND content_hash regen regressions.
- **Exit criterion:** `INTEGRATION=1 uv run pytest tests/integration/test_fresh_install_readiness.py -x -v` passes all 5 cases.
- **Risk:** low (test code; failures during dev are productive).
- **Rollback:** delete the test file.

**Phase 5 — CI workflow wiring**
- **Scope (in):** `.github/workflows/<quality-gate-or-tests>.yml`. Inspect existing workflows first to identify the right file.
- **Changes:** add a step running `INTEGRATION=1 uv run pytest tests/integration/test_fresh_install_readiness.py -x` to the quality-gate job (or equivalent). The step must run on PRs to `main`.
- **Exit criterion:** push branch with this change; CI workflow shows the new step running and passing on first run.
- **Risk:** low (standard CI yaml pattern).
- **Rollback:** revert workflow line.

**Phase 6 — Version bump 0.16.0 → 0.17.0 + CHANGELOG + tag**
- **Scope (in):** `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py` (5-file release sync per CLAUDE.md), `CHANGELOG.md`.
- **Version choice:** 0.17.0 minor. Justification: new top-level `memory:` key shipped in harness.yaml templates (schema growth, additive). Existing users migrate transparently via `_preserve_yaml_user_keys`. Deny baseline is purely additive via union. No breaking change but the schema surface grows.
- **Tag/push procedure (per CLAUDE.md release runbook):**
  ```
  git tag -a v0.17.0 -m "..."
  git push origin main v0.17.0
  ```
  Then **do nothing else** — the `release.yml` workflow runs `quality-gate → build → publish-testpypi → publish-pypi → github-release`. Do NOT manually `gh release create` (per documented 0.15.3 race regression).
- **Exit criterion:** tag-push completes; `gh run watch` for the release workflow reaches `github-release` job green; PyPI shows 0.17.0.
- **Risk:** low (release path well-rehearsed since 0.15.3).
- **Rollback:** if quality-gate fails, fix the regression in a new patch tag (0.17.1). PyPI / GitHub Release for v0.17.0 is immutable if it published.

## 🧪 Testing Strategy

- **Unit:** update `tests/unit/test_readiness.py` for new `_CONTEXT_LIMITS` values, new `_dim_verification` unknown-stack branch behavior, new `_dim_observability_setup` hint string. Snapshot tests for Side.yaml.j2 / Production.yaml.j2 / Side.json.j2 / Production.json.j2 rendered outputs (likely already exist; regen + commit).
- **Integration:** Phase 4 deliverable — `tests/integration/test_fresh_install_readiness.py` covers fresh install, existing-install migration via existing render path, and idempotency. Guard: `pytest.mark.skipif(not os.getenv("INTEGRATION"))`.
- **Manual (one-time, before tag):** in a scratch tmpdir, render a harness, simulate "user adds 5 telemetry samples" (touch metrics file with 5 lines), re-run readiness; verify `metrics_jsonl_present` and `metrics_has_samples` now surface as expected (allowlist gate releases at samples=5 per ADR-006).
- **Mock policy:** unit tests mock LLM where applicable (`mock_anthropic_client` fixture per CLAUDE.md test policy). Integration tests do not mock the render or readiness modules.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Existing pytest snapshot tests break due to template changes | high | medium | Phase 1+2 regen affected snapshots in same commit; visible in code review. |
| `_merge_permissions` union silently overwrites a user who set `deny: []` deliberately | medium | low | Accepted in ADR-005. The 4 baseline patterns are minimal security floor (rm/curl/etc/ssh) — re-adding them is correct security stance. |
| Skill trim (Phase 3) removes content that broke a downstream user expectation | low | low | Trim removes reference/internal blocks only; user-facing how-to retained; trim diff reviewed against an upstream skill consumer (search `autoloop-driver` references in repo before deleting blocks). |
| Unknown-stack weight drop hides regression in genuine Python project lacking pyproject.toml | low | medium | Per ADR-004 risk note: accepted. New stacks register via `_STACK_TESTERS`. |
| `composite_score` floor (Phase 4 exit) too tight or too loose | low | medium | Pin floor based on dev-time empirical measurement of fresh Side/Production render; record actual measured score in test docstring; adjust floor in PR review if needed. |
| Cursor/Codex users get partial benefit (Claude-side settings.json only) | medium | low | Explicit out-of-scope note in this PLAN. Cursor/Codex equivalents tracked as separate work. |
| Telemetry allowlist samples-based gate (ADR-006) regresses long-running projects | low | medium | Phase 4 test only asserts allowlist when samples < 5. Beyond 5, normal P0 surfaces — regression visible immediately. |
| Release version (0.17.0) confuses downstream PyPI consumers if `memory:` consumer code lands later | low | low | CHANGELOG entry explicitly notes "schema additive: `memory:` baseline shipped, consumer code in 0.18.x". |

## ✅ Success Criteria

- [ ] Fresh `/hm:make --preset Side` produces a harness whose `/hm:health` returns zero P0 outside `INTENDED_P0_SIGNALS` (telemetry × 2 + ci_workflow_present), with `composite_score ≥ 0.70`.
- [ ] Same for `--preset Production`, with `composite_score ≥ 0.75`.
- [ ] Existing user (0.15.x or 0.16.0) running `/hm:make` once gets `memory:` and the 4 deny patterns added transparently via existing render semantics; no `@hm:user:*` blocks touched.
- [ ] CI quality-gate runs the new integration test on every PR.
- [ ] Running `/hm:make` twice in a row on the same project produces byte-identical files (Phase 4 case 5 idempotency).
- [ ] Once a project accumulates 5 telemetry samples, `metrics_jsonl_present` and `metrics_has_samples` surface normally (no allowlist suppression).
- [ ] v0.17.0 released via tag-push only (no manual `gh release create`); PyPI shows the package.

## 🔍 Plan Validation

**Pass 1 (initial draft, 5 ADRs, 7 phases):** MAJOR_REVISION — 3 critical (Phase 4 yaml frontmatter handling unspecified, settings.json `deny: []` ambiguity, ADR-004 future-stack degradation), 8 warnings.

**Resolution (Follow-up Round, 4 questions):** chose hash-recompute + content-hash match + accept stack risk + opt-in `--upgrade` flag. Draft revised to add ADR-006 (content_hash) and ADR-007 (telemetry intended noise) — interim numbering.

**Pass 2 (revised draft, 7 ADRs, 7 phases):** MAJOR_REVISION — 2 critical (Phase 4 settings.json branch duplicates `_merge_permissions`, Phase 4 yaml branch duplicates `_preserve_yaml_user_keys` + render.py:602-603 hash recompute), 4 warnings.

**Resolution (Validation Round, 3 questions):** dropped Phase 4 entirely. Existing render semantics deliver migration; tests-only Phase 4 retained. Original ADR-005 (`--upgrade` flag) and ADR-006 (content_hash recompute) superseded by new single ADR-005 (use existing render semantics). ADR-007 became ADR-006 with samples-based TTL added.

**Final outcome: MAJOR_REVISION_RESOLVED via architectural redesign (not accept-as-risk).** All criticals addressed; remaining warnings either accepted with documented risk notes (ADR-004 future stacks, ADR-005 deny=[] overwrite) or resolved in the design (Phase 4 raw-bytes idempotency, ADR-006 samples TTL).

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->

<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
