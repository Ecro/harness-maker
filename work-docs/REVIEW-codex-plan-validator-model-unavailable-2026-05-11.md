---
type: review
task_slug: codex-plan-validator-model-unavailable
status: APPROVED
created: 2026-05-11
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
final_grade: A
iterations_used: 1
max_review_rounds: 3
human_review_needed: false
---

# REVIEW — codex-plan-validator-model-unavailable (2026-05-11)

## 🎯 Round 1 Summary

| Field | Value |
|-------|-------|
| Grade | **A** |
| Consensus-passed findings | 1 P2 |
| Weak-consensus findings | 1 P2 pair |
| Manual-only findings | 1 P1, 1 P2 |
| Drift findings | 1 (informational — auto-tooling) |
| Auto-fix applied | none (grade ≥ threshold A → STOP per gate) |

Threshold met. Status: **APPROVED**. Proceed to wrapup.

The fix is correct in mechanism: `model_codex=None` evaluates falsy under Jinja2 `StrictUndefined` so the `{% if model_codex %}` block elides; the gate is preserved for the deferred opt-in knob (per ADR-001). All findings are quality/maintenance signals, not bugs. The single P1 (manual-only) is a regression-guard gap worth fixing in a follow-up — see the §Manual-Only Findings explanation.

## 🔍 Drift Findings

| File | Phase scope? | Note | Severity |
|------|--------------|------|----------|
| `.claude/memory/session/2026-05-11.md` | NOT in any phase | Auto-managed by session tooling (writes per /hm:* invocation). Not user-authored. Informational only. | informational |

PLAN's Phase 3 claimed scope for `tests/e2e/{sandbox,sandbox-plugin-test}/.codex/agents/*.toml` — these paths do not exist as e2e fixtures. The execute stage recorded a scope correction in PLAN's §Execution Status. Not flagged as drift since the correction is auditable.

No phase has files that should have changed but did not (no incomplete phase).

## ✅ Consensus Findings

### P2 — `_CODEX_AGENT_META` value parentheses are visually indistinguishable from tuple literals

- **Reviewers**: code-reviewer, security-reviewer → strong consensus `[2/2]`
- **File**: `src/harness_maker/synthesize.py:142` (and lines 143–188 — all 12 entries follow the same pattern)
- **Tag**: `consensus-passed`

**OBSERVE** — each `_CODEX_AGENT_META` value uses Python implicit string concatenation inside parentheses:

```python
"autoloop-coder": (
    "Implementation agent for autoloop iterations — bounded scope, "
    "write-tool-only, no open-ended exploration; worktree-bounded writes"
),
```

This is a single `str` (parentheses for line continuation), but **visually** it is identical to a one-element tuple with a missing trailing comma — i.e. exactly the shape that caused the original `dict[str, tuple[str, str]]` bug that this fix removed.

**INFER** — a future edit (adding a third line, or re-introducing a `, "model"` second element on auto-pilot) can silently re-introduce the same shape error. `mypy --strict` would catch a true tuple at this declaration site (the annotation is `dict[str, str]`), but the type system cannot help the human reader who is editing the source.

**CONCLUDE** — readability/maintenance hazard of the same shape this PR just eliminated. Severity P2 (no current runtime risk; latent surface for re-introduction).

**Suggestion** (from reviewers; consensus-passed but NOT auto-applied per grade gate):
- Option A: switch each value to a triple-quoted string: `"""Implementation agent ..."""`.
- Option B: keep parens but add `# str, not tuple` on the first entry.
- Option C: remove parens and use `\` line continuation (less readable).

Recommend Option A or B — A is most idiomatic.

## ⚠️ Weak Consensus

### P2 weak — `synthesize.py:379` line, two distinct concerns

- **Reviewers**: code-reviewer + security-reviewer
- **File**: `src/harness_maker/synthesize.py:379`
- **Tag**: `weak-consensus` — surface match (same file + line + severity), CONCLUDE diverges
- **Keep both** — manual judgment required

**Finding 2a (code-reviewer)** — `dict(_CODEX_AGENT_META)` is a no-op identity copy. `_CODEX_AGENT_META` is already a `dict`; `dict(another_dict)` creates a shallow copy that is immediately consumed by the file-spec tuple and never mutated. Misleads readers into thinking mutation is a concern. Suggestion: replace with `_CODEX_AGENT_META` directly, or add an inline comment explaining the defensive copy intent.

**Finding 2b (security-reviewer)** — Description strings reach `config.toml.j2` via `dict(_CODEX_AGENT_META)` and are interpolated through Jinja2. The template at `templates/codex/config.toml.j2:6` uses `{{ agent_desc | tojson }}` which **does** auto-escape correctly today. Currently safe; flagged as fragile for future editors who might route user-supplied project metadata through this path. Suggestion: keep the `| tojson` filter; ensure `_render_pure_toml`'s `tomllib.loads()` validator stays as the safety net.

**Why kept separate**: the two findings address different risks at the same coordinates. Merging them would lose the distinction between "remove cosmetic noise" (2a) and "preserve template-escape pattern for future editors" (2b).

## 📝 Manual-Only Findings

### P1 manual — no unit test asserts `config.toml.j2` renders correctly with the new agent shape

- **Reviewer**: code-reviewer (single source)
- **File**: `tests/unit/test_synthesize.py` (gap) — actual missing test belongs in `tests/unit/test_codex_phase4.py`
- **Tag**: `manual-only`

**OBSERVE** — `_codex_target_files()` passes `{"agents": dict(_CODEX_AGENT_META)}` to `codex/config.toml.j2` (synthesize.py:379). The template (config.toml.j2:3-6) iterates `agents.items()` and renders `description = {{ agent_desc | tojson }}`. Existing tests in `tests/unit/test_codex_phase4.py` (`test_codex_config_toml_renders_valid_toml`, `test_codex_config_toml_has_features_section`, `test_codex_config_toml_mcp_servers_included`) all call `tpl.render(config=_BASE_CONFIG, agents={})` — they never exercise the loop body.

**INFER** — the new `dict[str, str]` shape produces TOML output equivalent to the pre-change tuple-extraction (`meta[0]`) at the template level (both shapes flatten to `{name: desc_string}` before reaching `config.toml.j2`). The change is semantically a no-op at the template input. However, the shape contract has zero regression coverage: a future revert of `_CODEX_AGENT_META` to `dict[str, tuple[str, str]]` that also reverts line 379's `dict(...)` back to `meta[0]` extraction would produce identical output; but a partial revert (only one site) would silently render `description = ["desc", "model"]` (TOML array) instead of a string. `tojson` would accept the array and produce valid TOML, so the bug would NOT raise at parse time.

**CONCLUDE** — Future-regression hazard at P1 severity is defensible; manual-only severity confined to "missing guard for a shape contract we just locked in". Not a current runtime bug.

**Recommended fix** (NOT auto-applied per grade gate):

Add to `tests/unit/test_codex_phase4.py`:

```python
def test_codex_config_toml_agents_section_renders_string_descriptions() -> None:
    """config.toml.j2 receives `{name: str}` (not `{name: tuple}`) — shape regression guard."""
    from harness_maker.synthesize import _CODEX_AGENT_META, _codex_target_files
    specs = _codex_target_files({})
    config_spec = next((ctx for tpl, out, ctx in specs if out == ".codex/config.toml"), None)
    assert config_spec is not None
    for name, desc in config_spec["agents"].items():
        assert isinstance(desc, str), f"agents[{name!r}] = {desc!r}, expected str"
```

Single-source so it does not affect Round 1 grade. If applied, run as a follow-up commit or fold into the wrapup PLAN's "Phase 5 (post-review)" if the user wishes.

### P2 manual — `_CODEX_MIN_CONFIG` in `test_synthesize.py:340` is a hand-rolled partial dict

- **Reviewer**: code-reviewer (single source)
- **File**: `tests/unit/test_synthesize.py:340-349`
- **Tag**: `manual-only`

**OBSERVE** — the new test's context fixture `_CODEX_MIN_CONFIG` omits keys that `HarnessConfig().model_dump(mode='json')` would supply. The current `agent.toml.j2` template only references `name`, `description`, `model_codex`, `reviewer_kind`, so the partial dict is sufficient for the specific assertion.

**INFER** — if the template ever accesses a new `config.*` key, the test would silently miss the failure (KeyError or Undefined). Replacing with `HarnessConfig().model_dump(mode='json')` removes the maintenance obligation.

**CONCLUDE** — Future maintenance hazard at P2 severity. Manual-only.

**Recommended fix** (NOT auto-applied):

```python
from harness_maker.models import HarnessConfig

# Replace the hand-rolled _CODEX_MIN_CONFIG with:
_CODEX_MIN_CONFIG: dict[str, Any] = HarnessConfig().model_dump(mode="json")
```

## 🤝 Disagreements

None. Reviewers agreed on every finding's severity (all P2 / P1 single-source). The weak-consensus pair at line 379 disagrees on **what the issue is**, not on severity.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)               | **A** | 0 (gate met)              | 1 consensus-passed P2 + 1 weak-consensus P2 + 1 P1 manual + 1 P2 manual | — |
| 2 (user-requested post-approval — "모두 개선해") | **A** | 4 (1 consensus-passed + 1 weak-consensus 2a + 2 manual-only) | 0 actionable; weak-consensus 2b is already in target state | 0 |

Final grade: **A**
Iterations used: 1 (initial) + 1 (user-requested follow-up) / 3
Status: **APPROVED**
human_review_needed: **false**

## Iteration 2 — User-Requested Cleanup (2026-05-11)

User invoked "모두 개선해" after review APPROVED status. All four actionable findings applied; the fifth (weak-consensus 2b) verified to already be in the target state.

| # | Finding | Fix Applied | File | Status |
|---|---------|-------------|------|--------|
| 1 | Consensus-passed P2 — `_CODEX_AGENT_META` parens-look-tuple (line 142) | Converted each of 12 values to plain `str` literal (no parens, no implicit-concat). Added a header comment explaining the visual-trap rationale. Lines exceeding 100 chars suppress E501 inline. | `src/harness_maker/synthesize.py:142-184` | Applied |
| 2 | Weak-consensus 2a P2 — `dict(_CODEX_AGENT_META)` no-op identity copy (line 379) | Replaced `dict(_CODEX_AGENT_META)` with `_CODEX_AGENT_META` directly. The template only reads `agents.items()`, no mutation surface. | `src/harness_maker/synthesize.py` (was line 379, now adjusted) | Applied |
| 3 | Weak-consensus 2b P2 — description→template escape fragility | **No fix needed** — `templates/codex/config.toml.j2:6` already uses `{{ agent_desc \| tojson }}` filter which auto-escapes TOML special chars. The `_render_pure_toml` path's `tomllib.loads()` validator is the secondary net. Current state matches the security-reviewer's target. | `src/harness_maker/templates/codex/config.toml.j2` (unchanged) | Verified — no action |
| 4 | P1 manual-only — no shape-regression guard for `config.toml.j2` agent shape | Added `test_codex_config_toml_agents_section_renders_string_descriptions` to `tests/unit/test_codex_phase4.py`. Asserts `_codex_target_files()` emits `{name: str}` for the config.toml `agents` context, covers all 12 agent keys, fails on shape revert. | `tests/unit/test_codex_phase4.py:200-243` | Applied |
| 5 | P2 manual-only — `_CODEX_MIN_CONFIG` hand-rolled partial dict | Replaced with `HarnessConfig().model_dump(mode="json")` — the test fixture now matches production exactly. | `tests/unit/test_synthesize.py:337-368` | Applied |

**Verification after Iteration 2:**
- `uv run pytest tests/unit/test_synthesize.py::test_codex_agent_toml_omits_model_field tests/unit/test_codex_phase4.py::test_codex_config_toml_agents_section_renders_string_descriptions -q` — 13/13 PASS.
- `uv run pytest tests/unit/ -q` — full suite GREEN.
- `uv run ruff check src/ tests/` — clean (initial `# noqa` directive in a comment caused a ruff parser warning; fixed by rephrasing the comment).
- `uv run ruff format --check` on edited files — clean.
- `uv run mypy --strict src/harness_maker/synthesize.py` — clean.
- `uv run python tests/snapshot/regenerate.py` — no `tests/snapshot/*.expected.yaml` diff (string literal vs implicit-concat are semantically identical → identical rendered output).
- Dogfood `.codex/agents/*.toml` and `.codex/config.toml` re-rendered surgically; `grep "^model\s*=" .codex/agents/*.toml` → 0 matches.

Final state: zero remaining findings of any severity. APPROVED stays APPROVED. Ready for wrapup.
