---
type: research
task_slug: second-brain-write-failure
status: complete
created: 2026-05-17
tags: [harness-maker, research, second-brain, obsidian, defect-analysis]
mtime_warn_days: 7
libs_fetched: []
sources:
  - file:src/harness_maker/second_brain.py
  - file:src/harness_maker/models.py
  - file:src/harness_maker/render.py
  - file:src/harness_maker/templates/harness-yaml/Production.yaml.j2
  - file:src/harness_maker/interview.py
  - file:tests/unit/test_second_brain.py
  - file:.claude/harness.yaml
related_docs: []
summary: "Three stacked defects — config-parser crash, empty folder allowlist, missing vault dir — make every Second Brain write fail."
---

# 🎯 Recommended Direction

**Fix `_load_config` first; the other two defects are masked by it.** Every Second Brain CLI invocation crashes before reaching folder/path logic, so the user never sees the downstream "folders not configured" or "vault missing" errors that would otherwise lead them to fix the config. The recommended sequence is (1) parse-frontmatter-aware loader, (2) explicit error or one-time interview prompt when `folders: []`, (3) actionable error message when `vault_path` does not exist on disk.

A single command attempt (`uv run python -m harness_maker.second_brain search 'harness' --type reference`) reproduces the failure end-to-end:
```
ERROR: expected a single document in the stream
  in "<unicode string>", line 2, column 1:
    generated_by: harness-maker
```

# 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (root cause in `src/harness_maker/second_brain.py`) and **Risk / compliance** (silent-failure surface — wrapup is supposed to persist durable memory but actually persists nothing).

`--deep` was not requested. Topic was specific (code-review the Second Brain pipeline + explain why Obsidian saves are missing), so Phase 0 / 0.5 interviews are skipped.

# 🛠️ Approaches Found

## Approach A — Frontmatter-aware loader in `_load_config`

| Field | Content |
|---|---|
| Approach | Replace `yaml.safe_load(...)` at `src/harness_maker/second_brain.py:232` with the same pattern used elsewhere in the repo: `yaml.safe_load_all(...)` (then pick the last document — convention used in `verify.py:34`, `worktree.py:315`, `rubric_loader.py:52`) **or** a `_strip_frontmatter` helper (`context_lint.py:42`, `autoloop_driver.py:233`). |
| Assumption | The rendered `harness.yaml` always carries a provenance frontmatter block emitted by `render.py:_format_frontmatter` (true since 0.1.x — fingerprint policy in CLAUDE.md §5 mandates it). |
| Evidence | (a) Live invocation: `yaml.safe_load` raises `yaml.composer.ComposerError: expected a single document in the stream`. (b) Test fixture `tests/unit/test_second_brain.py:30` writes harness.yaml with `yaml.safe_dump(payload)` and **no provenance frontmatter**, so unit tests never exercise the real file shape — this is why CI is green while production is broken. (c) Every other harness.yaml reader in the repo handles frontmatter. |
| Trade-off | Touching `_load_config` is a one-line fix but the test fixture must also gain frontmatter to prevent regression. |
| Compatibility | Fully backward-compatible (a single-doc YAML still parses; `safe_load_all` just returns one element). |
| Risk | low |

## Approach B — Default folder seeding when `folders: []`

| Field | Content |
|---|---|
| Approach | Either (i) auto-derive a sensible default like `[{path: "harness/{project_id}", read: true, write: true, note_types: [...]}]` when enabled + project_id set, or (ii) hard-error in `_load_config` with a one-line remediation telling the user to add a folder entry, or (iii) prompt for folders during `/hm:configure` instead of leaving "user adds them directly to harness.yaml" (current code path in `interview.py:469`). |
| Assumption | Users who set `enabled: true` + `vault_path` intend to write somewhere — `folders: []` is almost certainly an unfinished-configuration footgun, not an intentional read-only state. |
| Evidence | (a) `search_notes` silently returns `[]` when folders is empty (`second_brain.py:193-225` skips the loop body entirely); no error, no warning. (b) `write_note` raises `"{path} is not under a configured write folder"` (line 271) — confusing message that doesn't say "you haven't configured any folders". (c) `interview.py:469` comment: "the user adds them directly to harness.yaml after initial setup" — but no part of the wrapup/onboarding/configure UX nudges them to do this. |
| Trade-off | Auto-seeding (i) is more user-friendly but takes ownership of a directory layout decision; hard-error (ii) is safest but disrupts existing users. Prompt-during-configure (iii) is the most aligned with `/hm:configure` design. |
| Compatibility | Auto-seeding writes a new folder, which is observable on disk — requires the `@hm:user:*` block-merge boundary or a fingerprint check to avoid clobbering hand-edited folders. |
| Risk | medium (UX trade-off; not a code-correctness call) |

## Approach C — Vault-path existence check + early actionable error

| Field | Content |
|---|---|
| Approach | In `_load_config` (or `_vault_root`), call `Path(cfg.vault_path).expanduser().exists()` and raise `SecondBrainError("vault_path {x} does not exist — create the directory or run /hm:configure to fix")` when missing. Today the path resolves silently and only fails at `path.parent.mkdir(parents=True, exist_ok=True)` inside `write_note` (line 145) — which actually **succeeds** by creating the missing tree, meaning notes get written to a phantom location the user never opens in Obsidian. |
| Assumption | The current behavior of `mkdir(parents=True, exist_ok=True)` is itself a bug: it manufactures a `second-brain/` directory inside the vault that the user never asked for, and Obsidian's vault index won't even pick it up until they reload. |
| Evidence | (a) `/mnt/c/Users/euncheol.ro/Documents/obsidian-vault/second-brain` does not exist; the parent `obsidian-vault/` is a real Obsidian vault (has `.obsidian/`). The user said "obsidian 폴더를 지정했는데" — meaning they pointed Second Brain at a subfolder that the on-disk Obsidian vault treats as foreign. (b) `interview.py:479` warns "vault path {x} not found on this machine (registering anyway)" but only at interview time; nothing checks it at use time. |
| Trade-off | A hard "does not exist" error blocks legitimate first-write cases (creating the vault subdir intentionally). Mitigation: gate behind `mkdir_ok: false` flag, or require an explicit `--bootstrap` switch on first write. |
| Compatibility | Breaks any deployment that relies on the auto-mkdir behavior (likely none — there are no reports of files ending up in unexpected paths because the loader crashes first). |
| Risk | low |

# ⚠️ Pitfalls

1. **Test-fixture drift hides real bugs.** `tests/unit/test_second_brain.py:30` uses `yaml.safe_dump(payload)` to build the test harness.yaml. Real rendered harness.yaml carries provenance frontmatter (the file the loader actually sees in production). The unit tests are passing while production is 100% broken. Any fix must update the fixture builder to mirror real rendering, or add an integration test that uses `harness_maker.render`'s output directly.

2. **Multiple harness.yaml readers, multiple parser strategies.** Across the codebase: `verify.py` and `worktree.py` use `safe_load_all`; `autoloop_driver.py` and `context_lint.py` use a `_strip_frontmatter` helper; `second_brain.py` uses plain `safe_load`. The first two strategies are not 1:1 — `safe_load_all` returns each `---`-delimited doc as a separate dict, so consumers need to pick the right one (typically the last). A `harness_maker.io_utils.load_harness_yaml()` helper would prevent future drift.

3. **`folders: []` is a silent-success surface.** `search_notes` returns `[]` cleanly when folders is empty. Stage prompts (research, plan, wrapup) tell Claude to invoke `second_brain search` — Claude sees no error, sees no results, moves on, and never tells the user the connector is misconfigured. The wrapup template instructs `write` but is only a *suggestion* to the LLM; if the LLM doesn't try, the user never gets the actionable "folder not configured" error either.

4. **Auto-mkdir on write masks misconfiguration.** Once the loader is fixed, the second issue is that `path.parent.mkdir(parents=True, exist_ok=True)` (line 145) will silently create the missing `second-brain/` subfolder. The user will think saving works but Obsidian won't see the notes until they refresh the vault — and they may have intended a totally different folder. An explicit existence check before any write is safer.

5. **Provenance-frontmatter contract is invisible.** Templates like `Production.yaml.j2` and `Side.yaml.j2` don't emit `---` themselves — the renderer adds it. New consumers of `harness.yaml` will likely repeat the second_brain bug. Worth either documenting the contract explicitly in CLAUDE.md §"외부 소비자의 파서 정합성 확인" (it isn't currently called out for harness.yaml) or providing a helper.

# ❓ Open Questions

For `/hm:plan` to lock down:

1. **Loader strategy choice** — `safe_load_all + last` vs `_strip_frontmatter` helper vs new `io_utils.load_harness_yaml()`. Recommendation leans toward the helper-extraction approach because it centralizes the contract.

2. **Empty-folders policy** — hard-error, auto-seed default folder, or extend `/hm:configure` to require folder setup when `enabled: true`?

3. **Auto-mkdir policy** — keep current behavior, require explicit `--bootstrap`, or fail with actionable message when vault subdir is missing?

4. **Wrapup write contract** — is the wrapup template supposed to *strongly require* Claude to write notes (a real CLI gate that fails wrapup if writes were attempted but failed), or remain advisory? Today the wrapup never persists anything if the LLM skips the call, with no visible failure.

5. **Vault subfolder convention** — when the user types `/mnt/c/.../obsidian-vault/second-brain` but only `obsidian-vault/` exists, should `/hm:configure` infer the intent and offer to drop the `second-brain` suffix?

# 📚 Sources

- `src/harness_maker/second_brain.py:228-240` — `_load_config` uses `yaml.safe_load`.
- `src/harness_maker/second_brain.py:193-225` — `search_notes` silently returns `[]` when `folders: []`.
- `src/harness_maker/second_brain.py:252-271` — `_resolve_authorized` rejects every path when `folders: []` with the "not under a configured ... folder" error.
- `src/harness_maker/second_brain.py:140-147` — `write_note` invokes `mkdir(parents=True, exist_ok=True)` after passing the authorization gate.
- `src/harness_maker/render.py:64-65, 98` — provenance frontmatter is injected during render for harness.yaml.
- `src/harness_maker/templates/harness-yaml/Production.yaml.j2:1` — template body starts at `preset:`, no `---` in source.
- `src/harness_maker/verify.py:34`, `src/harness_maker/worktree.py:315, 340`, `src/harness_maker/rubric_loader.py:52` — `yaml.safe_load_all` precedent.
- `src/harness_maker/context_lint.py:42`, `src/harness_maker/autoloop_driver.py:233` — `_strip_frontmatter` precedent.
- `src/harness_maker/interview.py:465-488` — interview captures vault_path + project_id only; "user adds folders directly to harness.yaml".
- `tests/unit/test_second_brain.py:30-35` — test fixture writes harness.yaml without provenance frontmatter (regression gap).
- `.claude/harness.yaml:24-32` — current config: `folders: []`, `vault_path` points at non-existent subdir.
- Live filesystem: `/mnt/c/Users/euncheol.ro/Documents/obsidian-vault/` exists (real Obsidian vault, has `.obsidian/`); `obsidian-vault/second-brain/` does not exist.
- CLAUDE.md §"무언가를 고치거나 개선하기 전에" item 2: external-consumer parser-compatibility checklist — `harness.yaml`'s frontmatter contract is not currently listed there.

# 🔗 Related Internal Docs

- `.claude/memory/session/2026-05-11.md:102-103` — `[decision:user-workflow-opportunities-2026-05]` "Obsidian Second Brain uses project namespaces" (background on why writable folders must contain `project_id`).
- `.claude/memory/pending-drift.md:4` — recent Second Brain override-path patch (E501 split) — unrelated to current bug but shows recent activity in this module.

---

## Research saved → RESEARCH-second-brain-write-failure.md

**Topic:** Second Brain code review — why Obsidian saves never landed
**Recommended:** Approach A — fix `_load_config` to handle provenance frontmatter; then layer B/C on top.
**Sources fetched:** 0 web + 0 library docs + 12 internal refs (code + config + tests)
**Open questions for plan:** 5

**Ready to proceed?** Y/N
- Y → run `/hm:plan second-brain-write-failure` (will read this file via frontmatter)
- N → tell me which approach to dig deeper into, or which open question to answer first
