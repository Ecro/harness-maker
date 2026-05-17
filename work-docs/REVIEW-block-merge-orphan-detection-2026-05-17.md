---
type: review
task_slug: block-merge-orphan-detection
status: APPROVED
created: 2026-05-17
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
human_review_needed: false
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: block-merge-orphan-detection
  computed_at: 2026-05-17T23:30:00Z
  note: |
    No PLAN/SPEC exists for this change — derived ad-hoc from in-session
    investigation of a /hm:make --update silent data-loss bug (33 lines of
    user wiki content wiped). Drift gate not applicable.
---

## 🎯 Round 1 Summary

| | Value |
|---|---|
| **Final grade** | **A** (consensus-passed P0=0, P1=0) |
| **Status** | APPROVED (grade threshold met) |
| **human_review_needed** | **true** — 2 P1 manual-only findings warrant judgment before wrapup |
| **Iterations** | 1 / 3 (auto-fix loop not entered — no consensus-passed findings to fix) |
| **Mechanical checks** | unit suite 1925 passed / 8 failed (snapshot SHA mismatch from wrapup.md.j2 edit — needs regen) |

**Critical note** — Formal grade is **A** because no two reviewers independently flagged the same finding (surface + reasoning consensus). However, both P1 manual-only findings (security stdout-leak, code dedup-loss) are real, exploitable in narrow but credible scenarios, and worth addressing before commit. The consensus filter is deliberately strict (only fixes findings two reviewers agree on); the human owns the manual-only set.

## 🔍 Drift Findings

None. No PLAN exists for this work (in-session bug fix). Diff stays within the natural fix scope (block_merge core + cli display + wrapup template + tests + README image swap). See `drift_verdict` in frontmatter.

## ✅ Consensus Findings

None at any severity.

## ⚠️ Weak Consensus

### W1 — wrapup.md.j2 prose surface area (P2, weak)

**File**: `src/harness_maker/templates/stages/wrapup.md.j2:128–153`
**Reviewers**: code-reviewer (C-F5), security-reviewer (S-F5)
**Surface match**: ✅ same file, overlapping line range
**Reasoning alignment**: ❌ different concerns

- **code-reviewer take**: insertion instruction "above closing marker, blank-line separator" is unambiguous about WHERE but vague about HOW. A concrete `Edit(old_string=closing_marker, new_string=entry+closing_marker)` example would harden it.
- **security-reviewer take**: pre-existing risk — a user wiki entry whose body consists of `<!-- @hm:/user:entries -->` on its own line would prematurely close the user block on the NEXT merge. `_CLOSE_RE` matches markers on their own line with optional leading whitespace; a user paste could trigger this. Out of diff but worth documenting.

→ Both kept; recommend the Edit-example tightening (code) AND a note in the template documenting the "no bare close-marker lines in user content" invariant (security).

## 📝 Manual-Only Findings

### M1 — cli.py orphan preview leaks user content to LLM context (P1) 🔥

**File**: `src/harness_maker/cli.py:761–767`
**Reviewer**: security-reviewer (S-F1)

```
OBSERVE: New code does `preview = next((l.strip() for l in report.orphan_outside_content if l.strip()), "")[:60]`
         and emits `f"⚠ dropped {N} line(s) outside @hm:user:* blocks (first: {preview!r})"` via typer.echo.
INFER:   typer.echo → stdout → Bash tool result → next LLM turn's context. Whatever was the
         first non-blank dropped line (potentially a wiki entry body containing a hardcoded
         API key, ghp_/sk-ant-/AKIA token, password, or attacker-controlled "ignore previous
         instructions" payload) is verbatim ingested into the LLM's working memory on the
         next turn. 60-char truncation does not bound common token formats. The {preview!r}
         quoting adds backslash-escape but content is still parseable.
CONCLUDE: Stored prompt-injection + secret-disclosure vector opened by the very feature added
         to make the regression visible. Severity P1 because attack requires (a) user pasted
         secret outside the marker AND (b) running /hm:make --update — narrow but plausible.
```

> ⚠️ Security reviewer's original framing claimed the path was via the PostToolUse `*` hook. Verified: telemetry hook prints only `"ok"`; the actual path is direct (Bash tool result → LLM context, true for any CLI's stdout). Finding stands at P1.

**Suggestion**: Drop the preview entirely. Emit only count + path + remediation hint:
```python
bits.append(
    f"⚠ dropped {len(report.orphan_outside_content)} line(s) outside @hm:user:* "
    f"blocks — open the file and move content inside the marker, then re-run "
    f"/hm:make --update",
)
```

### M2 — block_merge.py set-based dedup loses duplicate orphan lines (P1)

**File**: `src/harness_maker/block_merge.py:493–499`
**Reviewer**: code-reviewer (C-F1)

```
OBSERVE: `new_outside_set = set(_collect_outside_marker_lines(new_text))` discards multiplicity.
         Filter: `[line for line in old_outside if line.strip() and line not in new_outside_set]`.
INFER:   If OLD has N copies of a line (e.g. `---`, `## Heading`, a blank-separator pattern that
         happens to match a template heading) and NEW has 1, all N are flagged "present" and
         dropped silently. Wiki entries appended below the closing marker often start with
         `## [wiki:...]` — if the template prelude were to ever contain a similar `##` line,
         multiple appended entries with that line would not be flagged.
CONCLUDE: False-negative in the very detection the helper was added to prevent. Severity P1.
```

**Suggestion**: Use Counter subtraction (preserves multiplicity):
```python
from collections import Counter
excess = Counter(old_outside) - Counter(_collect_outside_marker_lines(new_text))
report.orphan_outside_content = [
    line for line, count in excess.items() for _ in range(count) if line.strip()
]
```

### M3 — block_merge.py merge() walk fence-blind (P1, pre-existing)

**File**: `src/harness_maker/block_merge.py:460–477`
**Reviewer**: security-reviewer (S-F2)

```
OBSERVE: merge() main loop at L460-477 does not track fence state, unlike parse_segments (L186)
         and merge_inverted (L302) which both skip markers inside ``` fences.
INFER:   A NEW template file containing a fenced code block with a literal `<!-- @hm:user:foo -->`
         (e.g. documentation showing example markers) would trigger the merge walk's _OPEN_RE,
         causing _find_close (which IS fence-aware) to either raise ParseError or consume an
         unrelated close marker. parse_segments validates first and passes (fence-skip), so the
         downstream merge misbehaves silently for valid templates.
CONCLUDE: Validator/executor divergence. The test_block_merge.py inline comment at L361-365
         acknowledges this as known. Severity P1 by security reviewer; I'd call P2 in practice
         (requires template author to embed marker literals inside fences — narrow).
```

**Suggestion** (3 lines): mirror merge_inverted's fence tracking into the merge() walk:
```python
in_fence = False
while i < n:
    bare = _strip_eol(lines[i])
    if _FENCE_RE.match(bare):
        in_fence = not in_fence
        out.append(lines[i]); i += 1; continue
    if in_fence:
        out.append(lines[i]); i += 1; continue
    open_m = _OPEN_RE.match(bare)
    ...
```

### M4 — Missing test: template-prelude diff between OLD/NEW (P2)

**File**: `tests/unit/test_block_merge.py`
**Reviewer**: code-reviewer (C-F7)

The current orphan tests cover (a) bug repro, (b) identical-file no-FP, (c) blank-line handling. Missing: OLD has `# Header v1` (template-owned, outside markers) and NEW has `# Header v2`. Current algorithm WILL report `# Header v1` as orphan (correct — template-prelude lines also count). Without a test asserting this is intended, a future "fix" to ignore prelude differences would break the user content detection.

**Suggestion**: Add a `test_merge_orphan_outside_reports_template_prelude_change` test asserting `# Header v1` appears in `report.orphan_outside_content` after merge.

### M5 — Fence-blindness only tracked in inline comment (P2)

**File**: `tests/unit/test_block_merge.py:361–365`
**Reviewer**: code-reviewer (C-F8)

The comment "Out of scope for this P1 — separate follow-up" has no issue-tracker or memory-log anchor. Will rot across sessions and not surface in `/hm:health`.

**Suggestion**: Add a `[fail:render] merge-fence-blindness` entry to `.claude/memory/failures.md` (inside the `@hm:user:entries` block — per the new marker-discipline this PR enforces) referencing the test comment.

### M6 — wrapup.md.j2 wording could include concrete Edit-call example (P2)

**File**: `src/harness_maker/templates/stages/wrapup.md.j2:130`
**Reviewer**: code-reviewer (C-F5)

(See W1 — paired with security-reviewer's complementary concern as weak-consensus.)

### M7 — _collect_outside_marker_lines splitlines() vs parse_segments splitlines(keepends=True) doc nit (P2)

**File**: `src/harness_maker/block_merge.py:614`
**Reviewer**: security-reviewer (S-F3)

Not a bug (set-membership compares stripped lines on both sides — consistent). Suggestion: add a one-line comment at L614 documenting the intentional divergence.

## 🤝 Disagreements

None where reasoning aligned but severity differed.

**Implicit disagreement worth surfacing**: both reviewers identified fence-blindness as a real issue, but:
- code-reviewer treated it as P2 follow-up (comment-tracked)
- security-reviewer treated the same root cause as P1 correctness gap (M3)

This is not a consensus-filter pair (different files: test vs source). The user should decide which framing to act on.

## 📋 Mechanical Checks

| Check | Result | Notes |
|---|---|---|
| `uv run pytest tests/unit/` | ⚠️ 1925 passed, 8 failed | All 8 failures are `test_synthesize_snapshot.py::test_snapshot_matches[*]` — body sha256 of `commands/hm/exec-rev-wrap-ver.md` (and 7 other fused workflows) shifted because they embed the wrapup stage prompt I edited. Expected: needs `uv run python -m harness_maker.regenerate` (or equivalent snapshot regen). NOT a regression. |
| `uv run pytest tests/unit/test_block_merge.py` | ✅ 63/63 pass | Includes 3 new orphan-detection tests. |
| `uv run ruff check` | not run this round | Should run before commit. |
| `uv run mypy --strict` | not run this round | Should run before commit. |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 0 consensus / 7 manual / 1 weak | — |
| 2         | A     | 3 (M1+M2+M3 manual-applied)  | 0 consensus / 1 manual / 0 weak | 1 (cosmetic P2) |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: **false**

### Iteration 2 detail

Applied manually (per user direction, not via auto-fix loop — manual-only findings are not auto-fix eligible):

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Drop preview from MERGE_BLOCK orphan warning | `cli.py:760-771` | Applied — security reviewer confirmed user-controlled content fully removed from stdout |
| 2 | P1 | Counter-based dedup preserves multiplicity | `block_merge.py:34,512-517` | Applied — code reviewer confirmed `Counter.__sub__` drops keys ≤0 correctly |
| 3 | P1 | Fence-tracking added to merge() walk | `block_merge.py:475-483` | Applied — security confirmed parity with parse_segments; previously-removed fence test re-enabled |

Side actions:
- Added `test_merge_orphan_outside_counts_duplicates` test (M2 coverage).
- Re-enabled `test_merge_orphan_outside_skips_marker_lines_in_fenced_code` (M3 coverage).
- Regenerated 8 snapshot fixtures + 4 fixture CLAUDE.md (version stamp only) to absorb the wrapup.md.j2 prompt edit.
- Full unit suite: **1935/0 fail** (was 1925/8 fail before).

New Iter 2 finding (manual-only, P2 cosmetic):
- `block_merge.py:475` — `merge()` fence guard lacks `style is MarkerStyle.HTML_COMMENT` check. Both reviewers noted; security explicitly classified as "harmless because merge() has no style parameter and is HTML-only by construction." Carried as a one-line maintainer comment hint, not a blocker. Address with a single comment if future PR adds a `style` parameter to `merge()`.

Deferred to follow-up (P2 quality items from Iter 1):
- M4: template-prelude-diff orphan test
- M5: now obsolete — M3 fixed the underlying fence-blindness, no need for a `[fail:render]` entry
- M6: concrete Edit-call example in wrapup.md.j2
- M7: splitlines() doc nit in `_collect_outside_marker_lines`

## Recommended Pre-Commit Actions

The grade is A and auto-fix loop would not engage (no consensus-passed findings). But before wrapup commit, the user should consider the manual-only items in this order:

1. **M1 (P1 security — strong recommend)** — drop the preview from cli.py orphan warning. ~3 lines. Closes a stored-prompt-injection + secret-leak vector for a feature that doesn't need the preview to be useful.
2. **M2 (P1 correctness — recommend)** — switch set-based dedup to Counter subtraction in block_merge.py. ~5 lines. The detection works for the user's actual bug but has a documented false-negative class.
3. **Snapshot regen** — run regenerate to fix the 8 failing tests caused by the wrapup template edit.
4. **M3 (P1 fence-blindness)** — small (3 lines) and pre-existing; bundled in this PR or deferred is fine.
5. **M4–M7** — P2 quality items; defer or address as appetite permits.

<!-- @hm:user:procedure-extras -->
<!-- Project-specific Round 1 steps (extra reviewers, custom heuristics). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:procedure-extras -->

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items (additional invariants, domain rules). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->

<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the review stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
