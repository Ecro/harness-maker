---
type: plan
task_slug: auto-feedback-2026-05
status: complete
created: 2026-05-23
tags: [harness-maker, plan, telemetry, privacy, feedback-loop, opt-in]
research_doc: "[[RESEARCH-auto-feedback-2026-05]]"
interview_rounds: 3
adrs: 6
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Opt-in (default false) maintainer-dogfooding feedback module — in-band LLM judgment in wrapper templates writes local drafts; user manually submits via gh CLI"
---

# PLAN: auto-feedback-2026-05

## 🎯 Executive Summary

**What.** Add `harness.yaml.feedback.enabled: bool` (default `false`, togglable only via `/hm:configure` interview). When on, the 2 dispatcher wrapper templates (`atomic_command.md.j2`, `workflow_command.md.j2`) emit a Jinja-conditional tail block that asks the current turn's LLM to inspect the last telemetry stop event + matching tool-use rows, decide whether a harness-self issue occurred, and if so write a local draft to `.claude/observability/feedback/{YYYY-MM-DD}-{slug}.md` (dedup by hash). The dispatcher then prints a one-line footer with the exact `gh issue create --web --body-file <path>` command for the maintainer to run manually. When off, the Jinja branch is dead — zero file IO, zero token cost, byte-identical render to today.

**Why.** Maintainer dogfooding feedback loop. Pure-rule rubric needs code edit per new signal (CLAUDE.md "LLM 활용 원칙 최우선" conflict); out-of-band LLM call breaks `tests/unit/test_no_network.py` (ADR-005); opt-out default-on telemetry just got industry-burned in April 2026 (GitHub CLI v2.91.0 backlash). In-band LLM judgment in wrappers, opt-in default-off, gh-CLI-via-user transport: zero contract violations, full automation value.

**Key decisions (locked).**
- ADR-001: Default off, interview-only toggle, no `/hm:feedback` slash.
- ADR-002: `feedback:` new top-level axis (not under `adaptive:`).
- ADR-003: PRIVACY.md gains 1 anchored paragraph; "Nothing is transmitted" sentence stays literally true.
- ADR-004: Draft body field whitelist (5 fields: version+IDE+OS, stage+slug, trigger_signal, error_message (redacted), file_paths (.claude/ only)). Free-text markdown, not bug.yml-form-aligned.
- ADR-005: In-band LLM judgment in dispatcher wrappers (not stage bodies, not out-of-band call).
- ADR-006: Dedup by `hash(trigger_signal_id, slug, YYYY-MM-DD)` — skip-if-exists today, regenerate next day.

**Estimated impact.** ~8 new files, ~6 modified files, 7 phases, ~3 days serial work. Net surface change for non-maintainer users: 1 interview question (skippable), 0 behavior change.

## 📚 Prior Work

- `[[RESEARCH-auto-feedback-2026-05]]` — Approach D (maintainer-dogfooding opt-in) selected; 4 of 7 open questions locked in RESEARCH, 2 more locked in this PLAN (dedup, bug.yml mapping), 1 promoted to ADR-005 (in-band LLM).
- `[[PLAN-oss-readiness-audit]]` — ADR-004 (no opt-out env var) and ADR-005 (no-network positive obligation) are the binding constraints this PLAN must not violate. This PLAN's ADR-001 is the natural sibling: no opt-IN env var either; interview is the sole surface.
- `[wiki:milestone] personalization-depth-2026-05-shipped` — `AdaptiveConfig` already exists as telemetry-adjacent grouping; rejected for `feedback.enabled` because the semantic axis (bug reporting vs personalization learning) differs.
- `[wiki:fresh-install-health-baseline]` — `_merge_permissions` + `_preserve_yaml_user_keys` pattern. New `feedback:` key in harness.yaml templates uses the same additive baseline mechanism — no special migration code needed.
- `[wiki:gotcha] wrapup-marker-discipline-silent-loss` — informs Phase 6: PRIVACY.md paragraph + dispatcher block use explicit `@hm:` markers; grep assertions in snapshot tests.
- `[wiki:model-routing-multi-ide]` — informs Phase 5: interview question style + AliasChoices pattern (FeedbackConfig is simple enough to not need AliasChoices).

## 🎙️ Interview Transcript

| # | Round | Topic | Choice | → ADR |
|---|---|---|---|---|
| 1 | R0 (RESEARCH-locked) | Default + toggle surface + slash + transport | default off, interview-only, no slash, gh CLI | ADR-001 |
| 2 | R1.1 | harness.yaml axis location | `feedback:` top-level | ADR-002 |
| 3 | R1.2 | PRIVACY.md amendment scope | one paragraph (dead-branch invariant) | ADR-003 |
| 4 | R1.3 | Draft body fields | baseline 3 + error_message (redact) + .claude/ paths; reject tool-input snippet | ADR-004 |
| 5 | R2.1 | Trigger implementation | In-band LLM judgment (dispatcher wrapper) | ADR-005 |
| 6 | R3.1 | Dedup mechanism | hash(trigger_signal_id, slug, date) skip-if-exists today | ADR-006 |
| 7 | R3.2 | bug.yml mapping | Drop alignment claim; draft is free-text markdown | ADR-004 (amended) |

Round 1 batched 4 questions (3 single-select + 1 multi-select, all closed-form). Round 2 single question after presenting LLM-judgment trade-off analysis (token, test_no_network, determinism, false-positive iteration). Round 3 resolved 2 of 9 plan-validator critiques requiring user judgment (remaining 7 were engineering-detail fixes applied directly to PLAN body).

## 📐 Architecture Decision Records

### ADR-001: Maintainer-dogfooding opt-in; interview is the only toggle surface
**Status:** Accepted (2026-05-23, via /hm:plan interview R0+R1)
**Context:** Auto-feedback delivers value only to the maintainer who can act on signals; for all other users, the feature is noise at best, privacy risk at worst. April-2026 industry context: GitHub CLI v2.91.0 shipped opt-out default-on telemetry → Hacker News + The Register backlash for opaque redaction.
**Decision:** `harness.yaml.feedback.enabled: bool` defaults to `false`. The ONLY toggle surface is the `/hm:configure` interview. No CLI flag, no env var, no `settings.json` key, no `~/.harness-makerrc`.
**Consequences:**
- ✅ Non-maintainer users see zero behavior change.
- ✅ Mirror of [[PLAN-oss-readiness-audit]] ADR-004 ("no opt-out env var") — single-surface principle.
- ⚠️ Maintainer must remember to flip it back off before recording demos / sharing terminals.
**Rejected alternatives:**
- Opt-out default-on — Rejected: industry backlash 1 month ago (GitHub CLI v2.91.0).
- `HARNESS_MAKER_FEEDBACK=1` env var — Rejected: surface drift; violates the same single-surface principle that PLAN-oss-readiness-audit ADR-004 enforces for telemetry.
**Source:** Interview R0 (RESEARCH-locked) + R1.

### ADR-002: Single top-level `feedback:` axis (not under `adaptive:`)
**Status:** Accepted (2026-05-23, via /hm:plan interview R1.2)
**Context:** `AdaptiveConfig` already exists as a telemetry-adjacent grouping (`disable_telemetry`, `disable_audit`). Natural pull to nest `feedback_drafts: bool` there.
**Decision:** Add new top-level `feedback:` key with `enabled: bool` only. Future fields (`rate_limit`, `schema_version`) land additively under the same key.
**Consequences:**
- ✅ Semantic clarity: `adaptive` = personalization learning; `feedback` = bug reporting. Different intent surfaces should not share a config block.
- ✅ Cursor/Codex use identical key (single-source).
- ⚠️ One more top-level key in harness.yaml (minor schema-clutter cost).
**Rejected alternatives:**
- `adaptive.feedback_drafts: bool` — Rejected: semantic conflation.
- `feedback.enabled + feedback.allowed_fields:list` — Rejected: ship complexity escalation; allowed_fields belongs in the FeedbackDraft Pydantic model (single source of truth, AST-walk-drift-checkable).
**Source:** Interview R1.2.

### ADR-003: PRIVACY.md gains one anchored paragraph; existing transmission promise remains literally true
**Status:** Accepted (2026-05-23, via /hm:plan interview R1.3)
**Context:** Shipping a feedback module while PRIVACY.md says "Nothing is transmitted off your machine by this tool" risks weasel-wording accusations on first source reading.
**Decision:** Insert one paragraph after the existing "What is recorded" section, inside `<!-- @hm:privacy:feedback-module -->` markers. Paragraph states: (a) opt-in module ships in package, (b) `enabled: false` ⇒ dead Jinja branch ⇒ zero file/network IO, (c) when on, the only network call is `gh issue create --web` invoked by the user from the printed footer command — not by harness-maker. Existing transmission sentence is unchanged because both halves remain literally true.
**Consequences:**
- ✅ Pre-empts weasel-wording critique.
- ✅ AST-walk drift test (`tests/unit/test_privacy_doc_schema.py`) extended to cover `FeedbackDraft` Pydantic field list (see ADR-004 + Phase 6).
- ⚠️ Maintenance burden: every new whitelisted field requires PRIVACY.md schema-line + AST-walk test will fail loudly until updated.
**Rejected alternatives:**
- Dedicated "Feedback Module" section with full schema — Rejected: documentation burden disproportionate to maintainer-only use case.
- No edit — Rejected: surprise on code-reading.
**Source:** Interview R1.3.

### ADR-004: Draft body is free-text markdown with whitelisted field set; bug.yml alignment intentionally dropped
**Status:** Accepted (2026-05-23, via /hm:plan interview R1.4 + R3.2)
**Context:** `.github/ISSUE_TEMPLATE/bug.yml` requires structured fields (`reproduction`, `expected`, `actual`). `gh issue create --body-file` submits free-text that does NOT auto-populate form fields. Aligning the draft body to bug.yml form fields would require either extending the whitelist to LLM-generated `reproduction_hint`/`expected_hint`/`actual_hint` (additional fields → re-litigating the whitelist) or post-processing the body server-side (not possible from `gh --web`).
**Decision:** Draft body is free-text markdown with the following sections (in this order): (1) one-line title, (2) metadata header (`harness_maker_version`, `ide`, `os`, `stage`, `task_slug`), (3) trigger signal description (`trigger_signal.id` + count + duration_ms — numerical only), (4) optional error_message block (≤256 chars, run through `telemetry._SECRET_PATTERNS`), (5) optional file_paths block (filtered: each path MUST start with `.claude/`, else hard-rejected with `ValueError`). When the maintainer runs `gh issue create --web --body-file`, the browser opens with this markdown in the form's `body` field; maintainer manually copies portions into reproduction/expected/actual fields if desired.
**Allowed fields (Pydantic model `FeedbackDraft`):**
```python
class FeedbackDraft(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    harness_maker_version: str
    ide: Literal["claude-code", "cursor", "codex"]
    os: str  # platform.system() + release
    stage: str  # 7 atomic stages or workflow name
    task_slug: str
    trigger_signal: TriggerSignal  # nested: id/count/duration_ms (all numeric)
    error_message: str | None = None  # ≤256 chars, redacted
    file_paths: list[str] = Field(default_factory=list)  # .claude/ prefix only
```
**Consequences:**
- ✅ Simple; preserves 5-field whitelist (no scope creep).
- ✅ AST-walk drift test sees Pydantic field list, satisfies validator critique C3.
- ⚠️ Maintainer must do a 30-second manual copy if the bug template form fields are wanted.
**Rejected alternatives:**
- Extend whitelist with reproduction_hint/expected_hint/actual_hint — Rejected: additional fields re-open whitelist scope; LLM-generated hints risk hallucinating user-code references.
- Two-mode (free-text v1, structured v2) — Rejected: scope creep; defer until usage data shows the manual copy is actually painful.
- Tool input snippet (`_ALLOWED_TOOL_INPUT_KEYS`) — Rejected per Interview R1.4: whitelist rot risk per [wiki:fresh-install-health-baseline].
**Source:** Interview R1.4 + R3.2.

### ADR-005: In-band LLM judgment in dispatcher wrapper templates (no out-of-band socket call)
**Status:** Accepted (2026-05-23, via /hm:plan interview R2.1)
**Context:** Trigger classification ("is this a harness-self issue?") could be (a) pure-rule rubric, (b) out-of-band LLM call (`anthropic.Anthropic()`), or (c) in-band prompt block in the rendered command. CLAUDE.md "LLM 활용 원칙 (최우선)" says: "패턴 매칭·키워드 필터로 해결할 수 있는 것도, LLM 이 더 정확하게 판단할 수 있으면 LLM 에 위임." `tests/unit/test_no_network.py` (ADR-005 positive obligation in [[PLAN-oss-readiness-audit]]) monkey-patches `socket.socket` and forbids any socket call from our Python code.
**Decision:** In-band LLM judgment runs as a Jinja-conditional block in the 2 dispatcher wrapper templates: `templates/commands/hm/atomic_command.md.j2` and `templates/commands/hm/workflow_command.md.j2`. The block is a single `{% include "agents/_partials/feedback_dispatcher.md.j2" %}` guarded by `{% if feedback_enabled %}`. The included partial contains the prompt that instructs the current turn's LLM to (i) call `telemetry_grep.last_stop_with_trace()` via Bash (≤2KB output), (ii) decide if a harness-self issue occurred, (iii) if yes, call `draft_writer.write(...)` via Bash + emit the footer. Macro placed under existing `templates/agents/_partials/` (loader-discovered convention).
**Why wrappers, not stage bodies:** The 7 stage body templates under `templates/stages/*.md.j2` are pre-rendered in `synthesize._atomic_command_files` with a fixed Python context dict that does NOT include `feedback_enabled`. Inserting the conditional in stage bodies would silently no-op (validator critique C1). Wrapping at the wrapper layer is a 2-template touch instead of 7, AND the wrapper render context is already extensible. `synthesize.py` passes `feedback_enabled = harness.feedback.enabled` only to the 2 wrapper render calls.
**Consequences:**
- ✅ Zero socket call from our Python — `test_no_network.py` passes unmodified for `feedback/__init__.py` and `feedback/footer.py`. A new test function in Phase 2 covers `feedback/telemetry_grep.py` and `feedback/draft_writer.py` under the same socket trap.
- ✅ 2-template touch instead of 7; reduces Phase 4 snapshot regen blast radius.
- ✅ Stage bodies render context unchanged.
- ⚠️ Stochastic determinism (acceptable — maintainer-only, footer is informational; dedup by content-hash keeps duplicate visibility low).
**Rejected alternatives:**
- Pure rule rubric — Rejected: CLAUDE.md "LLM 활용 원칙" conflict; new signal requires code edit.
- Out-of-band `anthropic.Anthropic()` call from `feedback/*.py` — Rejected: violates `test_no_network.py` ADR-005 positive obligation; would require socket-trap carve-out (whitelist rot pattern).
- Inserting the conditional in 7 stage body templates — Rejected: validator critique C1 (synthesize.py render context omits `feedback_enabled`).
**Source:** Interview R2.1.

### ADR-006: Dedup by hash(trigger_signal_id, slug, YYYY-MM-DD); skip-if-exists today
**Status:** Accepted (2026-05-23, via /hm:plan interview R3.1)
**Context:** When `feedback.enabled: true`, every `/hm:*` command tail runs the LLM judgment block. A single hook error visible in today's `metrics-*.jsonl` will be detected by every subsequent command in the session — producing N duplicate drafts per real issue. RESEARCH listed this as a blocking open question; plan-validator W4 surfaced it as a critical gap.
**Decision:** `draft_writer.write(...)` computes `hash = sha256(trigger_signal_id + task_slug + today_date)[:16]` and constructs the filename as `.claude/observability/feedback/{YYYY-MM-DD}-{slug}-{hash}.md`. If a file with that exact path already exists, `write()` returns the existing path silently (no overwrite, no second draft, no footer emission). Next day, the date component changes and the same trigger produces a new draft — re-emergence of an unfixed issue is visible.
**Consequences:**
- ✅ One draft per issue per day; noise bounded.
- ✅ Deterministic key (sha256) — same trigger always hashes to same filename; idempotent write.
- ⚠️ A maintainer who already submitted yesterday's draft and is still seeing the bug today will get a fresh draft — acceptable (it signals the bug persists).
**Rejected alternatives:**
- No dedup — Rejected: noise explosion; maintainer fatigue.
- Time-window dedup (1h) — Rejected: date-boundary edge cases; harder to reason about.
**Source:** Interview R3.1.

## 🏗️ Technical Design

### Current state
- `src/harness_maker/telemetry.py` writes `metrics-{YYYY-MM-DD}.jsonl` with `_SECRET_PATTERNS` (sk-/ghp_/AKIA/Bearer) redaction + `_ALLOWED_TOOL_INPUT_KEYS` whitelist + 256-char cap.
- `src/harness_maker/review_telemetry.py` writes `review-{YYYY-MM-DD}.jsonl`.
- `src/harness_maker/observability/intent_miss.py` writes `silent-intent-miss-{slug}.jsonl`.
- `src/harness_maker/models.py:486` defines `HarnessConfig`; no `feedback` field yet.
- `tests/unit/test_no_network.py` monkeypatches `socket.socket` to raise; covers `emit_override`, `load_overrides`, `compute_yaml_diff`, `run_audit`, `sessionstart_drift`.
- `tests/unit/test_privacy_doc_schema.py` AST-walks `TELEMETRY_SOURCES` (Pydantic models + `_build_entry` dict-subscript) for PRIVACY.md schema sync; supports `kind='model'` and `kind='build_entry'`.
- `src/harness_maker/synthesize.py` `_atomic_command_files` pre-renders stage bodies and wraps them in `atomic_command.md.j2` (wrapper has its own render call with extensible context).
- `templates/commands/hm/atomic_command.md.j2` and `workflow_command.md.j2` are the 2 wrapper templates that produce all stage + fused-workflow commands.
- `.github/ISSUE_TEMPLATE/bug.yml` defines structured fields; `gh issue create --body-file` submits free-text (form fields not auto-populated).
- `templates/agents/_partials/` exists with includes like `communication_{variant}.md.j2`, `rubric.md.j2`, `reasoning.md.j2`, `hard_rules.md.j2` — established convention.

### New module: `src/harness_maker/feedback/`
- `__init__.py` — exports `FeedbackConfig`, `FeedbackDraft`, `TriggerSignal`.
- `telemetry_grep.py` — `last_stop_with_trace(metrics_dir: Path) -> str`: opens today's `metrics-{date}.jsonl` (file-IO only; no socket), finds last `stop` event, joins `post_tool_use` rows by `trace_id`, returns a ≤2KB serialized string. Asserts output size with `assert len(out) <= 2048` to enforce the budget at runtime.
- `draft_writer.py` — defines `TriggerSignal` and `FeedbackDraft` Pydantic models (5 whitelisted fields per ADR-004). `write(draft: FeedbackDraft, base_dir: Path) -> Path` does redaction (file_paths `.claude/` prefix check, error_message `_SECRET_PATTERNS` + 256 cap), computes dedup hash (ADR-006), atomic-writes via `io_utils.atomic_write`. Returns the path. Idempotent: if file with matching hash exists today, returns existing path without rewriting.
- `footer.py` — `render(draft_path: Path, locale: Literal["en", "ko"]) -> str`: returns one line per locale. Empty string when `draft_path is None`. en: `"📝 feedback draft saved → {path} (run: gh issue create --web --body-file {path})"`. ko: `"📝 feedback draft 저장됨 → {path} (실행: gh issue create --web --body-file {path})"`.

### Config model: `src/harness_maker/models.py`
```python
class FeedbackConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    enabled: bool = False

class HarnessConfig(BaseModel):
    # ...existing fields...
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
```
Reverse mapper: `interview.answers_from_harness_yaml` extracts `feedback.enabled` for re-render symmetry (CLAUDE.md checkpoint 6).

### Harness.yaml templates: `templates/harness-yaml/Side.yaml.j2` + `Production.yaml.j2`
Add at end of file (uncontroversial baseline location):
```jinja2
feedback:
  enabled: {{ (config.feedback.enabled if config.feedback else false) | lower }}
```
Re-render symmetry: `enabled: false` (most users) renders as `false`; explicit `enabled: true` (maintainer) survives `/harness-maker:make` regeneration.

### Dispatcher wrapper templates
Insert before the final closing fence in BOTH `atomic_command.md.j2` AND `workflow_command.md.j2`:
```jinja2
{% if feedback_enabled %}
{% include "agents/_partials/feedback_dispatcher.md.j2" %}
{% endif %}
```

### New partial: `templates/agents/_partials/feedback_dispatcher.md.j2`
```jinja2
<!-- @hm:feedback:dispatcher-block (do not edit; rendered by feedback.enabled) -->

---

## Feedback draft (maintainer dogfooding — opt-in)

After completing the stage above, run this Bash command to grep the last
telemetry stop event + matching tool-use rows (≤2KB output):

```bash
uv run python -m harness_maker.feedback.telemetry_grep --metrics-dir .claude/observability
```

Decide: is there evidence of a HARNESS-SELF issue (hook error, silent-intent-miss,
/hm:review build-break, plan-validator hang, dispatcher render regression, etc.)
that the maintainer would want to file as a GitHub issue against harness-maker
itself? Distinguish from user-code issues (their failing test, their slow build,
their syntax error) — those are NOT in scope.

If YES (harness-self issue):

1. Construct a `FeedbackDraft` (Pydantic model in `src/harness_maker/feedback/draft_writer.py`)
   using ONLY these whitelisted fields:
   - `harness_maker_version` (`harness_maker --version`)
   - `ide` (claude-code / cursor / codex)
   - `os` (platform.system() + release)
   - `stage` (this stage's name)
   - `task_slug` (from frontmatter, if present)
   - `trigger_signal` (TriggerSignal: id + count + duration_ms — numbers only)
   - `error_message` (≤256 chars, will be redacted by _SECRET_PATTERNS)
   - `file_paths` (list, ONLY paths starting with `.claude/` — others rejected)
2. Call `draft_writer.write(...)` via Bash:
   ```bash
   uv run python -m harness_maker.feedback.draft_writer --json <draft-json>
   ```
   The writer computes the dedup hash and either writes a new draft file or
   silently returns the existing path. Stdout: the resolved file path.
3. Emit the one-line footer (locale-aware) by reading the returned path:
   ```bash
   uv run python -m harness_maker.feedback.footer --path <path>
   ```

If NO: emit nothing.

NEVER include: user repo absolute paths, file content from the user's project,
command args verbatim, or any string that doesn't originate from the whitelisted
fields above.

<!-- @hm:/feedback:dispatcher-block -->
```

### Renderer wiring: `src/harness_maker/synthesize.py`
The render call sites for the 2 wrappers (currently `_atomic_command_files` ~lines 161-178 and the workflow_fuse path) pass `feedback_enabled = harness.feedback.enabled` into the wrapper render context dict. Stage body templates remain unchanged (no `feedback_enabled` in their render context — keeps them stable). Codex stage skills path (`_codex_stage_skills` ~lines 584-601) gets the same wrapper-level injection if it goes through a wrapper; if it renders stage bodies directly, the wrapper conditional is no-op for Codex (acceptable — Codex stage flow is independent).

### Interview wiring: `src/harness_maker/interview.py`
Add one question to the existing flow:
- Locale en: "Enable maintainer-dogfooding feedback drafts? Most users keep this OFF."
- Locale ko: "Maintainer dogfooding 용 feedback draft 활성화? 일반 사용자는 OFF 유지 권장."
- Options: [No (default, recommended for most users), Yes (maintainer dogfooding only)]
- Persisted to `feedback.enabled`.

### PRIVACY.md amendment
Insert after the existing "Where it's stored" section, inside markers:
```markdown
<!-- @hm:privacy:feedback-module -->
### Optional feedback module

harness-maker ships an opt-in feedback module (`feedback.enabled` in
`harness.yaml`, defaults to `false`). When `false`, the module is a dead
Jinja branch — zero file IO, zero token cost, zero behavior change. When
toggled on via the `/hm:configure` interview, a draft is written to
`.claude/observability/feedback/{YYYY-MM-DD}-{slug}-{hash}.md` containing
the fields documented in the `FeedbackDraft` Pydantic model
(`src/harness_maker/feedback/draft_writer.py`). The draft is local-only;
the only network call is `gh issue create --web` invoked by the maintainer
from the printed footer command — not by harness-maker.
<!-- @hm:/privacy:feedback-module -->
```

### Data flow when on
```
[/hm:research command run]
  → wrapper render with feedback_enabled=true
  → command body emitted (includes dispatcher partial)
  → LLM executes stage as normal
  → LLM hits the dispatcher partial: runs `telemetry_grep` via Bash
  → LLM judges: harness-self issue? Yes/No
  → If Yes: LLM calls draft_writer via Bash (returns path; dedup-skip safe)
  → LLM calls footer via Bash, prints one line
[turn ends]
[maintainer reads footer, manually runs `gh issue create --web --body-file <path>`]
[browser opens with body pre-filled, maintainer clicks Submit]
```

## 📝 Implementation Plan

### Phase 1 — Pydantic models + harness.yaml template rendering + reverse mapper
**Scope (in):** `src/harness_maker/models.py` (FeedbackConfig + HarnessConfig.feedback), `src/harness_maker/interview.py` (`answers_from_harness_yaml` reverse mapper extract), `templates/harness-yaml/Side.yaml.j2`, `templates/harness-yaml/Production.yaml.j2` (append feedback block), `tests/unit/test_models.py`, `tests/unit/test_interview_reverse_mapper.py`, `tests/unit/test_harness_yaml_render.py` (or extend existing).
**Scope (out):** `src/harness_maker/feedback/` module, dispatcher templates, draft writer.
**Exit criterion:**
- `uv run pytest tests/unit/test_models.py tests/unit/test_interview_reverse_mapper.py tests/unit/test_harness_yaml_render.py -v` passes.
- `uv run mypy src/harness_maker/models.py src/harness_maker/interview.py` clean.
- Snapshot test asserts: rendered Side.yaml contains `feedback:\n  enabled: false` block; rendered Production.yaml same; `answers_from_harness_yaml(parsed_harness_yaml)` round-trips `feedback.enabled=true` correctly (CLAUDE.md checkpoint 6).
**Risk:** low
**Rollback:** main.

### Phase 2 — Feedback module: telemetry_grep + no-network test
**Scope (in):** `src/harness_maker/feedback/__init__.py`, `src/harness_maker/feedback/telemetry_grep.py`, `tests/unit/test_feedback_telemetry_grep.py` (synthetic JSONL fixtures), `tests/unit/test_no_network.py` (add `test_telemetry_grep_no_network` function).
**Scope (out):** draft_writer, footer, dispatcher templates.
**Exit criterion:**
- Unit tests pass for: (a) hook-error stop event detection, (b) silent-intent-miss row inclusion, (c) build-break review row inclusion, (d) clean-session empty return, (e) ≤2KB output assertion enforced at runtime.
- New `test_telemetry_grep_no_network` in test_no_network.py monkey-patches `socket.socket`, calls `last_stop_with_trace()` with synthetic JSONL, asserts no `RuntimeError("ADR-005 violation: ...")` is raised. Passes.
- `uv run pytest tests/unit/test_no_network.py -v` shows the new test green.
**Risk:** low
**Rollback:** Phase 1.

### Phase 3 — Feedback module: draft_writer with Pydantic models + dedup + redaction
**Scope (in):** `src/harness_maker/feedback/draft_writer.py` (TriggerSignal + FeedbackDraft + write()), `tests/unit/test_feedback_draft_writer.py`, `tests/unit/test_no_network.py` (add `test_draft_writer_no_network`).
**Scope (out):** footer.py, dispatcher templates, PRIVACY.md.
**Exit criterion:**
- Snapshot tests assert: (a) draft frontmatter contains ONLY the 5 whitelisted fields (Pydantic `extra="forbid"`); (b) error_message containing `sk-XXX`, `ghp_XXX`, `AKIA...`, `Bearer ...` is `[REDACTED]`; (c) error_message >256 chars is truncated with `...<truncated>`; (d) file_paths containing `/home/user/...` raises `ValueError("path must start with .claude/")`; (e) two `write()` calls with identical (trigger_signal_id, task_slug, today) produce ONE file (dedup hash); (f) `freeze_time` produces byte-identical files across two runs.
- `test_draft_writer_no_network` asserts `write()` opens no socket.
- `uv run mypy src/harness_maker/feedback/` clean.
**Risk:** medium (redaction completeness — mitigated by reusing existing `_SECRET_PATTERNS` AND adding the regression-snapshot tests above).
**Rollback:** Phase 2.

### Phase 4 — Dispatcher partial + wrapper wiring + footer + render context propagation
**Scope (in):**
- `src/harness_maker/feedback/footer.py`
- `templates/agents/_partials/feedback_dispatcher.md.j2` (new partial; loader path verified via `templates/agents/_partials/` convention)
- `templates/commands/hm/atomic_command.md.j2` — replace the single-line passthrough (`{{ stage_body | default(...) }}`) with: passthrough + trailing `{% if feedback_enabled %}{% include "agents/_partials/feedback_dispatcher.md.j2" %}{% endif %}`
- `templates/commands/hm/workflow_command.md.j2` — append the same conditional `{% if feedback_enabled %}{% include %}{% endif %}` before the final fence
- `src/harness_maker/synthesize.py` — in the FileEntry construction loop at **lines 709-729** (per validator 2nd-pass anchor), add `"feedback_enabled": config_dump.get("feedback", {}).get("enabled", False)` to the per-file context merge. **Why global inject is safe:** Jinja `StrictUndefined` (per `render.py:65`) raises on variable ACCESS, not PRESENCE — templates that don't reference `feedback_enabled` are unaffected. This single modification covers both `_atomic_command_files` (lines 142-179) and `_workflow_command_files` (lines 433-453) output FileSpecs without touching either function. **Out of scope:** `_codex_stage_skills` (lines 573-602) and `_codex_workflow_skills` (lines 605-616) — Codex skills bypass both wrappers (use `codex/stage_skill.md.j2` / `codex/workflow_skill.md.j2` directly); Codex feedback support is a deferred follow-up PLAN (see Risk #8).
- `tests/unit/test_render_feedback_block.py` (new)
- `tests/unit/test_feedback_footer_i18n.py` (new)

**Scope (out):** PRIVACY.md, AST-walk drift test extension, interview wiring, Codex skill renders.

**Exit criterion:**
- Snapshot test `test_render_feedback_block` covers:
  - (a) **byte-identical-when-off:** When rendered with `harness.feedback.enabled=false`, the output of every FileSpec under `.claude/commands/hm/*.md` matches the existing `tests/snapshot/` fixture used by `tests/unit/test_synthesize_snapshot.py`. Use the same snapshot harness — `test_synthesize_snapshot` already covers wrapper render output across stage + workflow commands. Phase 4 ADDS a parametric variant with `feedback.enabled=false` that asserts the snapshot is unchanged from pre-Phase-4 main. **If the snapshot diffs**, the dispatcher Jinja block is leaking whitespace when off — fix the conditional placement (e.g., use `{%- if %}` to strip whitespace) before merging.
  - (b) **marker present when on, with fused workflow coverage:** Render with `harness.feedback.enabled=true` AND `InterviewAnswers.fused_workflows` containing at least one entry (e.g., the default `exec-rev-wrap-ver` workflow already used in `Production.yaml.j2`). Assert that BOTH (i) every atomic-command output AND (ii) every workflow_command output contains `@hm:feedback:dispatcher-block` exactly once. Empty `fused_workflows` would silently degenerate to atomic-only coverage — this fixture requirement prevents that false-pass.
  - (c) `grep -c '@hm:feedback:dispatcher-block' <rendered>` == 1 per file (markers neither duplicated nor missing — addresses Risk #7).
- Footer i18n test: en and ko strings match snapshots (frozen via test fixture).
- `uv run pytest tests/unit/test_render_feedback_block.py tests/unit/test_feedback_footer_i18n.py tests/unit/test_synthesize_snapshot.py -v` passes.

**Risk:** medium (synthesize.py modification surface — mitigated by exit criterion (a) byte-identical-when-off via the existing `test_synthesize_snapshot` harness; (b) fused_workflow fixture requirement prevents empty-coverage false-pass).
**Rollback:** Phase 3 (`git checkout -- templates/ src/harness_maker/synthesize.py src/harness_maker/feedback/footer.py`).

### Phase 5 — Interview wiring + locale-aware "maintainer dogfooding" copy
**Scope (in):** `src/harness_maker/interview.py` (insert question into existing flow), `src/harness_maker/i18n_messages.py` (en + ko strings), `tests/unit/test_interview_feedback_question.py`.
**Scope (out):** PRIVACY.md, AST-walk drift test.
**Exit criterion:**
- Test covers: (a) default `false` persisted when user picks "No"; (b) `true` persisted when user picks "Yes"; (c) question copy in both en + ko contains literal substring "maintainer dogfooding" / "maintainer dogfooding"; (d) round-trip via `answers_from_harness_yaml` preserves the value.
**Risk:** low
**Rollback:** Phase 4.

### Phase 6 — PRIVACY.md amendment + AST-walk drift test extension + CHANGELOG
**Scope (in):** `PRIVACY.md` (insert anchored paragraph after "Where it's stored"), `tests/unit/test_privacy_doc_schema.py` (add `FeedbackDraft` to `TELEMETRY_SOURCES` with `kind='model'`), `CHANGELOG.md`.
**Scope (out):** dispatcher templates, snapshot regen.
**Exit criterion:**
- `test_privacy_doc_schema.py` extended TELEMETRY_SOURCES entries:
  - `("src/harness_maker/feedback/draft_writer.py", "FeedbackDraft", "model")`
  - `("src/harness_maker/feedback/draft_writer.py", "TriggerSignal", "model")`
- PRIVACY.md schema section enumerates every field: `harness_maker_version`, `ide`, `os`, `stage`, `task_slug`, `trigger_signal`, `error_message`, `file_paths` (FeedbackDraft top-level) AND `id`, `count`, `duration_ms` (TriggerSignal nested).
- **Nested-model false-pass guard (validator C3 follow-up):** The existing backtick regex (`r'\`([A-Za-z_][A-Za-z0-9_]*)\`'`) at `test_privacy_doc_schema.py:84` would pass on TriggerSignal fields trivially because `id`/`count`/`duration_ms` are generic tokens likely to appear elsewhere in PRIVACY.md. Mitigation: the Phase 6 PRIVACY.md amendment places the TriggerSignal field list inside the `<!-- @hm:privacy:feedback-module -->` marker block as a fenced code block (```` ```yaml ... ``` ````) with comment lines naming each nested field. The test walker is extended with a **scoped check** that re-parses the marker block and asserts each TriggerSignal field name appears AT LEAST ONCE inside that block (not globally in PRIVACY.md).
- **Intentional regression test** (2 cases, both via tmpfile copies):
  1. Add field: in a tmpfile copy of `draft_writer.py`, add `extra_field: str = ""` to FeedbackDraft, re-run AST walker, assert `AssertionError` mentioning `extra_field` AND `PRIVACY.md missing schema entry`.
  2. Remove field documentation: in a tmpfile copy of `PRIVACY.md`, delete the `duration_ms` line from inside the feedback-module marker block, re-run the scoped check, assert `AssertionError` mentioning `duration_ms` AND `TriggerSignal field not documented in feedback-module block`.
- CHANGELOG.md entry under `[Unreleased]` documents: opt-in feedback module shipped, default off, PRIVACY.md amendment.

**Risk:** medium (drift test extension surface — mitigated by AST walker pattern already proven for OverrideRecord/ReviewTelemetryRecord/IntentMissEvent; nested-model false-pass mitigated by scoped marker-block check + 2nd regression test).
**Rollback:** Phase 5.

### Phase 7 — Snapshot regen + 5-file version bump + smoke test
**Scope (in):** all affected snapshots regenerated, `pyproject.toml` (version bump), `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `src/harness_maker/__init__.py` (__version__), `tests/integration/test_feedback_end_to_end.py` (INTEGRATION=1 gated).
**Scope (out):** none.
**Exit criterion:**
- Full `uv run pytest -x` green.
- `uv run ruff check && uv run ruff format --check && uv run mypy src/` all clean.
- 5-file version sync verified by `git grep` showing the new version in all 5 files.
- Integration test (INTEGRATION=1): (a) with `feedback.enabled: false`, run `harness-maker init` + simulate a /hm:research dispatch → assert zero files exist under `.claude/observability/feedback/`; (b) with `feedback.enabled: true`, write a synthetic `metrics-{today}.jsonl` with a hook-error stop event, run the dispatcher path → assert exactly 1 file appears under `.claude/observability/feedback/{today}-*-*.md` AND it contains the 5 whitelisted fields AND does NOT contain user repo paths.
**Risk:** medium (5-file version sync convention — established procedure, low novelty).
**Rollback:** Phase 6.

## 🧪 Testing Strategy

| Layer | Coverage |
|---|---|
| Unit (pydantic) | FeedbackConfig + FeedbackDraft + TriggerSignal validation (strict=True, extra=forbid) |
| Unit (telemetry_grep) | 5 fixtures: hook-error, silent-intent-miss, build-break, clean-session, 2KB cap |
| Unit (draft_writer) | 6 cases: whitelist, redaction, truncation, .claude/ enforcement, dedup, freeze_time |
| Unit (footer) | en + ko snapshot |
| Unit (render) | byte-identical-when-off snapshot, marker-present-when-on grep assertion |
| Unit (no-network) | Extended: test_telemetry_grep_no_network + test_draft_writer_no_network |
| Unit (interview) | round-trip via answers_from_harness_yaml |
| Unit (privacy schema) | Extended AST-walker with FeedbackDraft + TriggerSignal; intentional regression test |
| Integration (gated by INTEGRATION=1) | end-to-end with synthetic metrics-*.jsonl injection |
| Manual | maintainer flips on, runs /hm:research with contrived ambiguous topic, verifies footer + `gh issue create --web` browser preview |

## ⚠️ Risks & Mitigations

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Token budget regression: telemetry_grep returns >2KB | medium | Runtime `assert len(out) <= 2048` in `last_stop_with_trace`; unit test fixture exercises cap |
| 2 | LLM stochastic false-positive draft | low | Maintainer-only; footer is informational; dedup keeps duplicate visibility low; manual `rm` recovery |
| 3 | AST-walk drift test gap on new field | medium | Phase 6 extends test; intentional-regression test in same phase asserts the failure mode is loud |
| 4 | synthesize.py wrapper render context regression | medium | Phase 4 exit criterion (a) byte-identical-when-off snapshot catches accidental render changes |
| 5 | `_SECRET_PATTERNS` misses a novel secret format | medium | Reuse of existing well-tested patterns; 256-char cap as second line of defense; snapshot test exercises known formats (sk-/ghp_/AKIA/Bearer) |
| 6 | Maintainer accidentally turns on for demo/screencast | low | Interview copy explicitly says "maintainer dogfooding only — most users keep this off" in both en + ko |
| 7 | Block-merge marker discipline (wiki:wrapup-marker-discipline-silent-loss) | low (self-mitigated) | Both PRIVACY.md insertion and dispatcher block use explicit `@hm:feedback:dispatcher-block` / `@hm:privacy:feedback-module` markers; Phase 4 exit criterion (c) greps for marker count == 1 per rendered file |
| 8 | Codex stage skills bypass wrapper path | low (acknowledged & deferred) | Confirmed via synthesize.py lines 573-616: `_codex_stage_skills` uses `codex/stage_skill.md.j2` and `_codex_workflow_skills` uses `codex/workflow_skill.md.j2` — both bypass `atomic_command.md.j2` / `workflow_command.md.j2`. Phase 4 conditional is no-op for Codex. **Deferred to follow-up PLAN** if maintainer uses Codex as primary IDE; current PLAN scope is Claude Code + Cursor only. Codex users who flip `feedback.enabled: true` will see no behavior change (same as `false`). |
| 9 | Pydantic `extra="forbid"` rejects legitimate future field additions | low | Same pattern as existing telemetry models; field additions go through the AST-walk drift test loop (Phase 6) |
| 10 | Wrapper render context propagation skipped for one of the 2 wrappers | medium | Phase 4 exit criterion (b) requires marker present in BOTH atomic + workflow command outputs |

## ✅ Success Criteria

- [x] `feedback.enabled` defaults to `false` in models, harness.yaml templates, and renderer.
- [x] When `false`: rendered output under `.claude/commands/hm/` is byte-identical to pre-PLAN main.
- [x] When `true`: harness-self event triggers exactly one draft per day per (trigger_signal_id, task_slug) tuple.
- [x] PRIVACY.md "Nothing is transmitted off your machine by this tool" sentence remains in the file, unchanged.
- [x] `tests/unit/test_no_network.py` passes with TWO new test functions added (`test_telemetry_grep_no_network` + `test_draft_writer_no_network`); existing functions unchanged.
- [x] AST-walk drift test catches an undocumented new field via the intentional-regression test in Phase 6.
- [x] Generated draft contains zero strings from user repo content — `file_paths` `.claude/` enforcement test passes; error_message redaction snapshot test passes.
- [x] `harness-maker --version` matches `pyproject.toml` matches all 3 plugin.json files matches `__init__.py`.
- [x] CHANGELOG entry under `[Unreleased]` documents the new opt-in module.

## 🔍 Plan Validation

**First pass:** MAJOR_REVISION (9 critiques: 3 critical, 5 warnings, 1 suggestion).
**Resolution:**
- Critical C1 (synthesize.py scope) → ADR-005 amended: wrapper-level placement (2 templates), synthesize.py modification surface enumerated in Phase 4.
- Critical C2 (`_macros/` directory missing) → use existing `templates/agents/_partials/` convention; loader change unnecessary.
- Critical C3 (AST-walker kind mismatch) → FeedbackDraft + TriggerSignal as Pydantic models with `kind='model'`; satisfies existing AST walker pattern.
- Warning W4 (dedup missing) → ADR-006 added (Interview R3.1); Phase 3 scope extended.
- Warning W5 (bug.yml mapping gap) → ADR-004 amended (Interview R3.2): free-text markdown; bug.yml form alignment dropped.
- Warning W6 (template count "11" wrong) → corrected throughout; wrapper-level placement (2 wrappers) covers all stage + workflow command outputs.
- Warning W7 (harness.yaml templates omitted) → Phase 1 scope extended (Side.yaml.j2 + Production.yaml.j2).
- Warning W8 (test_no_network contradiction) → resolved: "extended" wins; Success Criteria updated to "TWO new test functions added; existing functions unchanged".
- Suggestion S9 (block-merge marker risk self-mitigated) → Risk #7 downgraded to low; Phase 4 exit criterion (c) adds grep assertion.

**Second pass:** Returned MAJOR_REVISION (12 findings: 3 critical, 6 warnings, 3 suggestions). Of the prior 9: 7 GENUINELY RESOLVED (C2, W4, W5, W6, W7, W8, S9), 2 PARTIALLY RESOLVED (C1 needed exact line citation; C3 needed nested-model false-pass guard). 3 NEW findings surfaced, all engineering-detail (no architectural change required).

**Resolution (incorporated into this PLAN body without 3rd validator pass, per user decision):**
- C1 follow-up → Phase 4 scope now cites exact line ranges (synthesize.py 709-729 for FileEntry context merge; 142-179 and 433-453 for wrapper FileSpec producers; Codex bypass paths 573-616 explicitly out of scope).
- C3 follow-up → Phase 6 nested-model false-pass guard: TriggerSignal fields documented inside `<!-- @hm:privacy:feedback-module -->` marker block as a fenced YAML schema; AST-walker scoped check verifies each field name appears inside that block (not globally); 2nd intentional regression test asserts removal of `duration_ms` from marker block raises `AssertionError`.
- NEW C → covered by C1 follow-up (same fix).
- NEW W1 (snapshot fixture name) → Phase 4 exit (a) names `tests/snapshot/` + `tests/unit/test_synthesize_snapshot.py` as the existing harness; adds parametric `feedback.enabled=false` variant; whitespace-leakage failure mode documented with `{%- if %}` mitigation.
- NEW W2 (Codex bypass + fused_workflow fixture) → Phase 4 exit (b) requires `InterviewAnswers.fused_workflows` populated (e.g., `exec-rev-wrap-ver`); Risk #8 amended to "acknowledged & deferred — Codex follow-up PLAN".

**Validator outcome:** MAJOR_REVISION_RESOLVED (per user-approved fix incorporation; 3rd pass intentionally skipped).
