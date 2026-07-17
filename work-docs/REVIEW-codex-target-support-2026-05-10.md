---
type: review
task_slug: codex-target-support
status: APPROVED
created: 2026-05-10
reviewers_invoked: [code-reviewer, security-reviewer, performance-reviewer, concurrency-reviewer, ux-reviewer]
consensus_method: cross-check (2/3 surface+reasoning)
grade: A
human_review_needed: false
---

# Review: codex-target-support

## 🎯 Round 1 Summary

| Metric | Value |
|--------|-------|
| Grade | **A** |
| Consensus-passed P0 | 0 |
| Consensus-passed P1 | 0 |
| Weak-consensus | 1 pair |
| Manual-only | 18 findings |
| False positives invalidated | 2 |
| Auto-fix applied | No (grade ≥ threshold) |
| Status | **APPROVED** |

All 5 reviewers ran. No finding reached cross-reviewer consensus-passed status — meaning no two reviewers identified the same execution risk at the same code location. Grade A is earned by the absence of consensus-passed P0/P1, but several individually identified findings warrant developer attention before the next release.

---

## 🔍 Drift Findings

No drift detected. All changed files are within PLAN-codex-target-support.md Phase 1–9 scope:
- `src/harness_maker/{models,synthesize,render,reconcile,context_lint,io_utils}.py`
- `src/harness_maker/gates/permission_gate.py`
- `src/harness_maker/templates/codex/`
- `tests/unit/test_codex_phase{1–7,9}.py`, `test_render.py`, `test_synthesize_codex.py`
- `.codex-plugin/plugin.json`, `pyproject.toml`, `__init__.py`, plugin manifests
- `CLAUDE.md`, `tests/codex-compat/`

---

## ✅ Consensus Findings

*None.* No pair of findings from different reviewers aligned on both surface location (same file, line ±5 or named symbol) AND execution risk (CONCLUDE clause). Grade A stands.

---

## ⚠️ Weak Consensus

### WC-1 — `backup()` incomplete for new Codex paths
**Tag:** `weak-consensus` | **Severity:** P2 | **File:** `reconcile.py`

| Reviewer | Line | Finding |
|----------|------|---------|
| code-reviewer | 213 | `backup()` backs up `.claude/`, `.cursor/`, `.codex/`, `AGENTS.md` but NOT `.agents/`. Re-render of skill files has no rollback point. |
| concurrency-reviewer | 225 | TOCTOU between `while candidate.exists()` loop and `shutil.copytree` — concurrent process could create `candidate` between check and copy. |

**Surface match:** Same named function `backup()`, same file `reconcile.py`, both P2. ✓  
**Reasoning alignment:** code-reviewer CONCLUDE = "incomplete backup scope"; concurrency-reviewer CONCLUDE = "race condition on candidate path". Different execution risks — **weak consensus**.  
**Action:** Both are valid concerns; both require manual judgment on fix approach.

---

## 📝 Manual-Only Findings

### Security

#### M-SEC-1 — TOML injection via MCP server name  
**Severity:** P0 | **Reviewer:** security-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/templates/codex/config.toml.j2:5`

```toml
[mcp_servers.{{ server_name }}]
```

`server_name` is interpolated directly into a TOML dotted-key section header. A name containing `.` (e.g., `evil.nested`) creates `mcp_servers["evil"]["nested"]` instead of `mcp_servers["evil.nested"]` — valid TOML that passes `tomllib.loads()` validation but produces unexpected structure. A name with `]` produces invalid TOML that `_render_pure_toml()` will catch and raise `ValueError`.

**Risk context:** `server_name` comes from user-authored `harness.yaml` (not external attacker input), so this is a misconfiguration risk rather than a remote exploit. However, a user who configures an MCP server named `server.name` would silently get wrong nesting.

**Suggested fix:** Quote the key using TOML bracket-string syntax:
```toml
[mcp_servers."{{ server_name }}"]
```
This handles dots, spaces, and all non-identifier characters safely.

---

#### M-SEC-2 — PermissionRequest path is gated on attacker-controlled field  
**Severity:** P0 | **Reviewer:** security-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/gates/permission_gate.py:97`

```python
hook_event = str(payload.get("hook_event_name") or "")
...
if hook_event == "PermissionRequest":
    behavior = "allow" if decision.allow else "deny"
    print(json.dumps({...}))
    return 0
```

**Post-verification analysis:** After reading the code end-to-end, the risk is narrower than P0. For a dangerous Bash command, `evaluate()` returns `allow=False`, so the PermissionRequest path correctly emits `"deny"`. The theoretical bypass exists only if an attacker can inject `hook_event_name = "PermissionRequest"` into a PreToolUse payload — but Claude Code generates this field from the actual event type; it is not user-injectable. Downgraded from P0 to **P1 (theoretical)** by reviewer analysis. Leaving as M-SEC-2 for completeness.

**Suggested hardening:** Validate that `hook_event_name` is one of the expected values (`PreToolUse`, `PermissionRequest`) and reject unknown values. Adds defense-in-depth.

---

#### M-SEC-3 — `evaluate()` allows all non-Bash tool names  
**Severity:** P1 | **Reviewer:** security-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/gates/permission_gate.py:64`

`evaluate()` only inspects `tool_name == "Bash"`. For PermissionRequest events where `tool_name` is `write_file`, `apply_patch`, or similar, the gate unconditionally returns `allow=True`. This is intentional by ADR design (Bash-only gate) but was flagged as incomplete for the Codex context where PermissionRequest covers all tool types.

**Risk context:** The PLAN specified the gate as a Bash-only safety net. Extending it to all tools would require per-tool deny-lists. Low risk if the Codex sandbox restrictions already cover file writes.

---

#### M-SEC-4 — `rm_rf` regex missing word boundary  
**Severity:** P2 | **Reviewer:** security-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/secscan/hook_injection.py:13`

The `rm_rf` danger pattern may not have a word boundary, allowing `firm_raf_config` or similar to produce false positives. No false negatives identified. Low impact.

---

### Code Correctness

#### M-CODE-1 — Codex fast-paths missing in reconcile: TOML files always KEEP  
**Severity:** P1 | **Reviewer:** code-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/reconcile.py:101`

`reconcile()` has explicit fast-paths for `hooks.json`, `.cursor/hooks.json`, `.sh` files, and `AGENTS.md`. Codex TOML files (`.codex/config.toml`, `.codex/agents/*.toml`) have no fast-path. They fall through to `parse_frontmatter()`, which returns `None` (pure TOML has no YAML frontmatter), triggering the `KEEP` decision.

**Effect:** Re-rendering a project that has Codex target installed will never update `.codex/config.toml` or agent TOML files, even when templates change. Template improvements to these files will not propagate on `hm:make`.

**Suggested fix:** Add a fast-path for TOML files (like the `.sh` and `hooks.json` fast-paths):
```python
if str(fe.path).endswith(".toml"):
    conflicts.append(ConflictItem(path=fe.path, decision=ReconcileDecision.REPLACE, reason="pure-toml-no-frontmatter"))
    continue
```

---

#### M-CODE-2 — AGENTS.md block-merge: reconcile sets MERGE_BLOCK, render bypasses it  
**Severity:** P1 | **Reviewer:** code-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/reconcile.py:87` + `src/harness_maker/render.py:560`

`reconcile()` correctly returns `MERGE_BLOCK` for `AGENTS.md` (line 87–94). But in `render()`, `_is_agents_md(fe)` routes to `_render_agents_md()` which writes the template output directly — it does not call `_try_block_merge()`. The MERGE_BLOCK decision is computed but never honored.

**Effect:** User-edited `<!-- @hm:user:project-rules -->` and `<!-- @hm:user:extensions -->` blocks in AGENTS.md are silently overwritten on re-render.

**Suggested fix:** In `render()`, when `fe.path == Path("AGENTS.md")` and the file is in `merge_paths`, call `_try_block_merge()` before writing. This requires `_try_block_merge` to handle HTML-comment metadata lines (currently it only strips YAML frontmatter — see M-CODE-3).

---

#### M-CODE-3 — `_try_block_merge` / `_split_existing_frontmatter` unaware of HTML-comment metadata  
**Severity:** P1 | **Reviewer:** code-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/render.py:509`

`_split_existing_frontmatter()` strips `---\n…\n---\n` YAML blocks. AGENTS.md starts with `<!-- harness-maker: content_hash=... -->` (HTML comment). `_split_existing_frontmatter` would correctly return `("", full_text)` (no YAML preamble). But `_try_block_merge` passes `old_body` (including the HTML comment line) to `block_merge()`. If `block_merge()` treats the HTML comment as content rather than metadata, it would appear in merged output under `<!-- @hm:user:* -->` sections rather than being stripped.

**Dependency:** This only fires if M-CODE-2 is fixed. Currently latent.

---

#### M-CODE-4 — `backup()` does not include `.agents/` directory  
**Severity:** P2 | **Reviewer:** code-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/reconcile.py:213`

`backup()` snapshots `.claude/`, `.cursor/`, `.codex/`, and `AGENTS.md` but not `.agents/` (the skill dual-render directory). After a backup+restore, `.agents/skills/` would be left in the post-render state rather than the pre-render state. Related to WC-1 weak-consensus.

---

#### M-CODE-5 — `context_lint._strip_frontmatter` unaware of HTML-comment metadata  
**Severity:** P2 | **Reviewer:** code-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/context_lint.py:42`

`_strip_frontmatter()` removes YAML `---` blocks before counting lines. AGENTS.md uses an HTML-comment first line for metadata. The HTML comment line is counted toward the lint threshold, slightly inflating the measured line count. Low impact: the threshold is 200/500 lines, and the HTML comment is 1 line.

---

### Performance

#### M-PERF-1 — `os.fsync` on every `atomic_write` serializes ~100 writes on WSL2/NTFS  
**Severity:** P1 | **Reviewer:** performance-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/io_utils.py:21`

`atomic_write()` calls `os.fsync()` before `os.replace()`. On WSL2/NTFS (the primary development platform per CLAUDE.md), each fsync takes 5–50ms. Rendering a 58-file blueprint costs 290ms–2.9s in fsync alone, serialized. Linux ext4 fsyncs are ~1ms, so this is a WSL2-specific regression.

**Risk context:** fsync is intentional for crash safety (CLAUDE.md §Atomic file write). Trade-off between correctness and speed. For a harness generator (run infrequently), 1–3 seconds is acceptable. If render time becomes a pain point, consider batching all writes and fsyncing the directory once, or making fsync opt-in.

---

#### M-PERF-2 — `tomllib.loads()` validation result discarded  
**Severity:** P2 | **Reviewer:** performance-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/render.py:282`

The parsed TOML dict from `tomllib.loads(rendered)` is discarded — the result is used only to validate syntax. Not a correctness issue. Optimization: the parsed dict could be used to extract metadata instead of re-parsing later.

---

### Concurrency

#### M-CONC-1 — TOCTOU in `backup()` candidate path  
**Severity:** P2 | **Reviewer:** concurrency-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/reconcile.py:225`

See WC-1 above. The `while candidate.exists()` loop and subsequent `shutil.copytree` are not atomic — a concurrent process could create `candidate` in the gap. Low probability in practice (microsecond timestamp + counter). Related to WC-1 weak-consensus.

---

#### M-CONC-2 — `fe.body_sha256` mutation in `_render_pure_toml`  
**Severity:** P2 | **Reviewer:** concurrency-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/render.py:288`

`_render_pure_toml()` mutates `fe.body_sha256 = body_hash` on a `FileEntry` that is part of the Blueprint. If Blueprint files were rendered concurrently (not currently the case), this mutation would be a race. Presently render() iterates sequentially — latent risk only.

---

### UX / Template Correctness

#### M-UX-1 — AGENTS.md omits `@hm-spec` and `@hm-verify` from stage list  
**Severity:** P1 | **Reviewer:** ux-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/templates/codex/AGENTS.md.j2:9`

Current line 9:
```
Run individual stages: `@hm-research`, `@hm-plan`, `@hm-execute`, `@hm-review`, `@hm-wrapup`.
```

`@hm-spec` and `@hm-verify` are atomic stages (in `_ATOMIC_STAGES`) but are absent from this user-facing reference. Codex users who want spec-driven or post-execute verification are not told these skills exist.

**Suggested fix:**
```
Run individual stages: `@hm-research`, `@hm-spec`, `@hm-plan`, `@hm-execute`, `@hm-review`, `@hm-verify`, `@hm-wrapup`.
```

---

#### M-UX-2 — AGENTS.md mislabels `verbosity` config as `consensus`  
**Severity:** P1 | **Reviewer:** ux-reviewer | **Tag:** `manual-only`  
**File:** `src/harness_maker/templates/codex/AGENTS.md.j2:13`

Current line 13:
```
consensus: `{{ config.reviewers.verbosity }}` — code, security, performance, concurrency, and UX reviewers available.
```

The label `consensus:` is misleading — the value shown is `config.reviewers.verbosity` (e.g., `normal`). The word "consensus" has a specific technical meaning in the review system (consensus-passed vs manual-only). This line should either show the verbosity setting under a `verbosity:` label, or show the consensus method.

**Suggested fix:**
```
verbosity: `{{ config.reviewers.verbosity }}` — code, security, performance, concurrency, and UX reviewers available.
```

---

#### M-UX-3 — Minor UX issues in AGENTS.md template (P2)  
**Severity:** P2 | **Reviewer:** ux-reviewer | **Tag:** `manual-only`

- `@hm-` prefix convention is not explained in AGENTS.md.j2 (line 7) — users unfamiliar with harness-maker don't know these are Codex skills.
- `.claude/harness.yaml` cross-target reference (line 21) could clarify what keys to change.
- Block-merge markers (`<!-- @hm:user:* -->`) are not explained inline — users may not know they can edit these sections.
- Stage skill SKILL.md has a forward reference to the stage's "full procedure" which lives in the skill file, not AGENTS.md — the reference currently dead-ends.

---

## 🤝 Disagreements

No cross-reviewer severity disagreements identified (all findings were single-source).

---

## 🔎 False Positives Identified

Two findings from reviewers were invalidated by code inspection:

| Finding | Reviewer | Claim | Verdict |
|---------|----------|-------|---------|
| `synthesize.py:203` | code-reviewer P2 | `_CODEX_AGENT_META[n]` KeyError — not all agents covered | **FALSE** — `_CODEX_AGENT_META` and `_ALL_AGENTS` both list the same 12 agents. No KeyError possible. |
| `reconcile.py:237` | concurrency-reviewer P2 | `backup()` copies AGENTS.md to uninitialized `candidate` dir when `.claude/` absent → FileNotFoundError | **FALSE** — `backup()` is only called from `cli.py` when `target_dotclaude.exists()`. When `.claude/` exists, `shutil.copytree(existing_dir, candidate/existing_dir.name)` creates `candidate` before AGENTS.md is copied. |

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 0         | —   |

**Final grade: A**  
**Iterations used: 1 / 3**  
**Status: APPROVED**  
**human_review_needed: false**

---

## Recommended Follow-up Actions (not blocking wrapup)

These are high-value fixes for future iterations, ranked by impact:

| Priority | Finding | Effort |
|----------|---------|--------|
| High | M-CODE-1: Add TOML fast-path in reconcile so Codex config updates propagate | 3 lines |
| High | M-UX-1: Add @hm-spec and @hm-verify to AGENTS.md stage list | 1 line |
| High | M-UX-2: Fix verbosity/consensus label mismatch in AGENTS.md | 1 line |
| High | M-SEC-1: Quote MCP server name in TOML section header | 1 line |
| Medium | M-CODE-2: Wire block-merge into AGENTS.md render path | ~20 lines |
| Medium | M-CODE-4: Add .agents/ to backup() scope | 3 lines |
| Low | M-SEC-2/3: Harden PermissionRequest gate for non-Bash tools | design decision |
| Low | M-PERF-1: Make fsync opt-in for WSL2 performance | flag needed |
