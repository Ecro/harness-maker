---
type: review
task_slug: untested-trio-review-2026-05-19
feature: second_brain
status: complete
created: 2026-05-19
reviewer: Claude solo (ADR-002 amended)
plan: "[[PLAN-untested-trio-review-2026-05-19]]"
summary: "Deep review of harness_maker.second_brain — Obsidian-backed typed-note CLI. Live exercise + 473 LOC + 442 LOC unit + 240 LOC e2e + 4 stage templates."
---

# REVIEW — `second_brain` (harness-maker)

## Live-exercise preamble (paths + observations)

**Fixtures used:**
- vault: `/home/noel/obsidian-vault/` (Linux local, no sync — confirmed Phase 0)
- writable folder: `harness-maker/hm-review-fixture-2026-05-19/` (under vault; nested `harness-maker/` segment is mandatory per `_write_folders_are_project_namespaced`)
- backup: `/tmp/harness.yaml.pre-phase0.bak` (sha256 `7aaea53a...`)

**Files written during exercise (cleaned in Phase 5):**
- `harness-maker/hm-review-fixture-2026-05-19/fixture-decision.md`
- `harness-maker/hm-review-fixture-2026-05-19/fixture-preference.md`

**Notable observations:**
1. **Three cascading validation errors** before a first successful write: (a) folder path missing `harness-maker` segment, (b) folder path was `harness-maker-hm-review-fixture-...` (substring not segment) — still rejected, (c) frontmatter missing `created`/`updated`. Each error message was clear in isolation, but the cumulative friction surface for a first-time user (or an LLM agent on the wrapup stage) is high.
2. **Successful happy path** once the schema was learned: write decision + preference notes round-trip cleanly. Search by query / by `--type` works. Read returns the full file with frontmatter intact.
3. **Boundary attempts** all blocked correctly: path traversal (`../../../../tmp/escape-test.md`), write outside configured folder (`other-project/escape.md`), unknown note type (`random-thing`). Errors actionable.
4. **`search "" --tag X`** rejects with "search query cannot be empty" — but tag-only listing is a natural use case (find all my decisions).
5. **Validate output diverges from write output**: `validate` omits the project namespace warning that `write_note` emits — inconsistency.

## Methodology

Solo deep read + 7-item self-critique gate per ADR-002 (amended). Live exercise covered all 6 CLI subcommands (`write`, `read`, `search`, `append`/`patch` indirectly via write, `validate`). Read scope: `src/harness_maker/second_brain.py` (473 LOC) end-to-end; `SecondBrainConfig` / `SecondBrainFolder` / `SecondBrainNoteType` validators in `models.py` (L268-L367); both test files (`tests/unit/test_second_brain.py` 442 LOC; `tests/integration/test_second_brain_e2e.py` 240 LOC); all 4 stage template integration points (`plan.md.j2`, `research.md.j2`, `review.md.j2`, `wrapup.md.j2`).

Finding count: **17 (1 critical, 4 major, 4 minor, 8 info)**. Severity floor (≥ 3) met without escalation; consensus-arbiter not invoked.

## Correctness

### C1 — `created`/`updated` are required but never auto-filled · `Severity: major`
**Where:** `second_brain.py:87-90` enforces `required = ["type", "created", "updated", "tags", "links"]`. The `write_note` API takes a fully-formed `frontmatter` dict — no defaulting layer.
**Why it bites:** Every caller (CLI, stage templates, wrapup stage) must supply ISO-8601 timestamps themselves. The wrapup template (`wrapup.md.j2:49-53`) instructs LLMs to "use the CLI" with no example schema; an LLM will hit `ERROR: missing required frontmatter: created, updated` on first try.
**Reproduction (live):** `python -m harness_maker.second_brain write … --frontmatter-json '{"type":"decision","tags":["hm/second-brain"],"links":[]}' --body-file foo.md` → exit 1.
**Suggested fix (for a future fix-PLAN):** auto-inject `created` (file mtime or wall-clock UTC) and `updated` (wall-clock UTC) in `write_note` before `validate_note(...)` if missing. Keep the validator strict for already-on-disk notes.

### C2 — Project-isolation validator rejects path *substring* matches but message says "path segment" · `Severity: minor`
**Where:** `models.py:362` — `if self.project_id not in Path(folder.path).parts`.
**Live finding:** I first tried `harness-maker-hm-review-fixture-2026-05-19` (concatenated). The error message ("must include project_id 'harness-maker' as a path segment") is technically accurate but readers commonly equate "contains" with "substring". Clearer wording: "must contain `'harness-maker'` as a `/`-separated path component (e.g. `'harness-maker/your-folder'`)".

### C3 — `search` rejects tag-only queries · `Severity: major`
**Where:** `second_brain.py:201-202` — `if not query.strip(): raise SecondBrainError("search query cannot be empty")`.
**Why it bites:** "Show me all my preferences" is a stage-template use case (`plan.md.j2` filters by `--type preference`). The procedure currently *requires* a query string; an LLM passing `""` will be rejected. Workaround is to pass a dot or wildcard, but that ends up as substring-matching against unrelated content.
**Suggested fix:** allow empty query iff `note_type` OR `tag` is provided; iterate vault and return all matching the filter.

### C4 — Note-type folder allowlist works · `Severity: info` (no defect — confirming behavior)
**Where:** `second_brain.py:217-218` (search), `:323-327` (`_ensure_type_allowed` in write).
**Confirmed:** Folder with `note_types=[DECISION]` rejects `failure` writes AND silently skips `failure` notes during search. Matches test coverage. No finding.

### C5 — `write_note` silently overwrites existing files · `Severity: major`
**Where:** `second_brain.py:154` — `atomic_write(path, _format_note(...))`. No existence check, no `--force` flag.
**Why it bites:** Wrapup-stage automatic note-writing (`wrapup.md.j2:38-54`) could clobber a manually-written user note at the same path. Append/patch exist as alternatives but require knowing the path was already taken.
**Suggested fix:** `write_note(..., overwrite: bool = False)` — raise if `path.exists() and not overwrite`. CLI exposes `--force`.

### C6 — Smart-vault detection (ADR-002) behaves as documented · `Severity: info`
**Where:** `second_brain.py:259-284`. Tested by `tests/unit/test_second_brain.py:281-341`.
**Confirmed:** missing subdir + parent has `.obsidian/` → warn + accept; parent without `.obsidian/` → loud error. Sound design. No finding.

## Boundary & mock-reality gap

### B1 — Mock harness.yaml shape matches production (provenance frontmatter) · `Severity: info` (gap closed)
**Where:** `tests/unit/test_second_brain.py:30-53` `_write_harness_yaml` mirrors `render._format_frontmatter`'s shape verbatim, including the leading multi-doc `---` block. This was the gap that caused PLAN-second-brain-write-failure (ADR-005). The fixture-vs-production parity is **good**.
**Caveat:** the fixture uses a *fake* `content_hash` (64 zeros). Doesn't catch a hash-validation regression. Not a finding here — there isn't a hash validator path through `_load_config`.

### B2 — Path traversal blocked at resolution layer · `Severity: info` (passes)
**Where:** `second_brain.py:296-315` `_resolve_authorized` uses `Path.resolve()` + `Path.is_relative_to(root)`. Both unit-tested and confirmed live (`../../../../tmp/escape-test.md` → error).

### B3 — Live observation: `vault_path` in shipped `harness.yaml` does not exist on this machine · `Severity: major`
**Where:** `.claude/harness.yaml:44` ships as `/mnt/c/Users/euncheol.ro/Documents/obsidian-vault/second-brain` — a WSL-host-specific path. This machine has the vault at `/home/noel/obsidian-vault/`. Phase 0 had to temp-override `vault_path`.
**Why it bites:** Anyone on a non-WSL machine, or a different WSL host, picks up `second_brain.enabled: true` from `Production.yaml.j2` defaults but cannot use it. The "smart vault" check (C6) will fail loudly ("vault parent is not an Obsidian vault") and the user has to discover that the *default* config baked a personal path.
**Suggested fix:** the default in `Production.yaml.j2` should leave `vault_path: ""` and require the interview to set it, OR set `enabled: false` until the user runs `/hm:configure`.

### B4 — Mock tests do not exercise concurrent writers · `Severity: minor`
**Where:** `atomic_write` is used (good) but no test simulates two `write_note` calls racing. `tempfile.mkstemp` + `os.replace` is POSIX-atomic for the final rename, but the prior `parent.mkdir(parents=True, exist_ok=True)` is not race-free under directory creation. Likely benign in single-process LLM use; documenting for completeness.

### B5 — No mock for very large note (≥ MB-scale) · `Severity: info`
The CLI reads `--body-file` via `Path(...).read_text(encoding="utf-8")` (`:447`, `:451`). A multi-MB note loads fully into memory. No paging. Not exercised by tests. Not a defect for the intended use case (concise notes).

### B6 — Non-ASCII / Korean note titles not exercised · `Severity: info`
Title extraction (`second_brain.py:385-392`) uses `str.startswith("# ")` and `.strip()` — Unicode-safe. Search uses `.lower()` which handles Latin only correctly. Korean queries would match by raw substring (likely fine). Not tested. Project locale defaults to `ko` per `harness.yaml:10` — non-ASCII filename test gap is more visible here than in generic projects.

## Security & permission posture

### S1 — No shell injection vector in CLI · `Severity: info` (passes)
**Where:** `_cli` (`:405-465`) — `argparse` parses, file reads via `Path.read_text`, no `subprocess` or `shell=True`. JSON parsed by `json.loads`. Frontmatter is `yaml.safe_load` (not `yaml.load`). Output via `print(json.dumps(...))`. No injection surface.

### S2 — Folder `.write=false` enforced at resolution time · `Severity: info` (passes)
**Where:** `_resolve_authorized:308-310`. Verified live.

### S3 — `..` segments rejected in folder *path config* AND at runtime resolution · `Severity: info` (passes, defense-in-depth)
**Where:** `models.py:296-297` (config-time), `second_brain.py:313` (runtime via `.is_relative_to`). Both layers. The `models.py` validator cites "REVIEW-2026-05-17 security finding" — good provenance.

### S4 — `vault_path` from harness.yaml is `expanduser()`'d and treated as trusted absolute · `Severity: minor`
**Where:** `_vault_root:288` does `Path(cfg.vault_path).expanduser()`. A user with a tampered `harness.yaml` could set `vault_path: /etc` and then writable folders rooted at `/etc/...`. Mitigated by:
- folder paths must be relative (not absolute) per `SecondBrainFolder` validator
- folder `write=true` requires `project_id` as path segment, narrowing the target
- vault parent must contain `.obsidian/` (C6) — `/etc` would fail that

So effectively self-defending, but the `harness.yaml`-trust posture is worth noting: anyone with write access to `harness.yaml` can pivot vault to a different absolute path. Acceptable for the local single-user model. Document explicitly somewhere.

### S5 — `project_id` slug validator regex is strict · `Severity: info` (passes)
`models.py:350` `^[a-z][a-z0-9-]{0,63}$`. Blocks shell metacharacters, NUL, slashes, dots. Solid.

## Integration boundary

### I1 — `wrapup.md.j2` instructs LLMs to write notes but provides no schema example · `Severity: critical`
**Where:** `src/harness_maker/templates/stages/wrapup.md.j2:38-54` says "Use `!uv run python -m harness_maker.second_brain write ...`" with no `--frontmatter-json` example. The CLI requires a JSON object with `type`, `created`, `updated`, `tags`, `links` plus type-specific recommended fields. An LLM following the template will hit one or more of: (a) missing-frontmatter error, (b) project-segment violation, (c) folder allowlist rejection, before producing a valid write.
**Confirmed live:** my own Phase 1 exercise reproduced this cascade in the role of the wrapup-stage LLM.
**Why it bites:** wrapup's intent is automatic, durable note-writing as a side-effect of finishing work. If the LLM fails the first write call and the wrapup stage has no retry budget, durable notes are silently dropped. The user does not see a defect — wrapup completes "successfully" with no Second Brain output.
**Suggested fix (must include in fix-PLAN):** wrapup.md.j2 should include a worked example block per `note_type` showing frontmatter shape, OR `second_brain.py` should auto-fill `created`/`updated`/required tags so a minimal `{"type":"journal", "title":"..."}` call succeeds.

### I2 — Stage templates do not check folder write-eligibility before calling write · `Severity: major`
**Where:** All four stage templates assume `second_brain.enabled: true` implies "I can write". But `_load_config` may return cfg with `folders=[]` (graceful degrade, ADR-008). `write_note` then raises with a `/hm:configure` pointer (good), but the stage template has no try/except wrapper — the wrapup procedure would fail mid-stage on a degraded config.
**Suggested fix:** wrapup pre-check should call `validate` against a non-existent path or read `cfg.folders` length, surface a single human-readable warning, then proceed without writing.

### I3 — Search-only stage templates degrade safely · `Severity: info`
`plan.md.j2`, `review.md.j2`, `research.md.j2` only invoke `search`. Per `tests/unit/test_second_brain.py:366-385`, `search_notes` with `folders=[]` returns `[]` + log warning. Safe to call.

### I4 — CLI writes warnings to stdout (mixed with JSON) — no stderr separation · `Severity: major`
**Where:** `_print_write_result:468-469` prints `{"path": ..., "warnings": [...]}` as JSON to stdout. Errors go to stderr. But the LLM consuming this in a stage template parses the stdout as JSON; warnings are accessible but undifferentiated from success. If the LLM only inspects the file path field, warnings (e.g. `"recommended project namespace missing"`) are lost.
**Suggested fix:** mirror warnings to stderr too, OR add `--quiet` / `--warnings-as-stderr` flags. Document in CLI help.

### I5 — `__init__` lazy loading: `harness_maker.second_brain` imports `harness_maker.models` which imports a lot · `Severity: info`
First-time `uv run python -m harness_maker.second_brain --help` is ~700 ms on this machine (subprocess + Python startup). Adds latency to every stage template invocation. Not a defect; informational for perf tuning.

## UX & observability

### U1 — Error messages are clear in isolation but cumulative friction is high · `Severity: major`
**Confirmed via live exercise:** three sequential errors before first successful write (cascade documented in preamble). Each individual message is OK; the *path of least resistance* to a successful note-write is not obvious. A getting-started guide / worked example in the README or `commands/hm/configure.md` would help.

### U2 — No `--verbose` / `--quiet` flags · `Severity: minor`
All outputs are equally loud (warnings printed alongside successful write JSON). No way to suppress warnings for scripted use.

### U3 — `validate` subcommand omits the project-namespace warning that `write_note` emits · `Severity: minor`
**Where:** `_cli:457-461` calls `validate_note(fm, body)` only — doesn't call `_project_namespace_warnings`. `write_note` does (`:152`). Inconsistent surface.
**Suggested fix:** factor a `full_validate(harness_root, frontmatter, body)` that includes the project-namespace check; `_cli` calls it.

### U4 — No telemetry / structured logging hooks · `Severity: info`
Standard library `logging.getLogger(__name__)` used. No metrics, no JSON-formatted events, no observability hooks. Acceptable for the local-only design (CLAUDE.md "100% local telemetry — no external transmission"). Logging at WARNING level for degraded states (folders=[], smart-vault accept) is appropriate.

### U5 — `search` `limit=20` is hard-coded · `Severity: minor`
**Where:** `search_notes:198`. No CLI flag exposes it. A vault with >20 matching notes silently truncates.
**Suggested fix:** `--limit` flag (default 20), and emit a warning in result when limit was hit.

## Docs drift

### D1 — `CLAUDE.md §Stage-Aware Second Brain` is rendered into stage templates but not standalone-documented · `Severity: info`
The behavior is described once per stage template. There is no top-level doc explaining the "decision/preference/failure/project/reference/journal" type taxonomy or when to write which. README does not mention Second Brain. New users have to read the stage templates to discover the feature.

### D2 — `Production.yaml.j2` ships personal `vault_path` baked in · `Severity: major` (overlap with B3)
Confirmed by Phase 0 — see B3. This is both a config and a docs issue: the default in the template documents a private path.

### D3 — `commands/hm/configure.md.j2` references second_brain but content gap unclear from rendered config · `Severity: info`
Did not exercise `/hm:configure` live in this review. Likely the right place to surface vault path + folder setup walk-through. Note for fix-PLAN: when fixing B3/D2, verify that `/hm:configure` provides the path-setup interview question.

## Test gaps

| # | Gap | Why missing matters | Suggested test |
|---|-----|---------------------|----------------|
| T1 | `write_note` overwriting existing file (related: C5) | Wrapup auto-writes can clobber user notes | `test_write_note_refuses_overwrite_without_force` (after C5 fix) |
| T2 | Concurrent writers (related: B4) | Background wrapup vs interactive write race | `test_concurrent_writes_serialize_via_os_replace` |
| T3 | CLI bad JSON in `--frontmatter-json` | `json.JSONDecodeError` caught at `:462` but not asserted | `test_cli_write_rejects_invalid_json` |
| T4 | Search with regex special chars (`.`, `[`, `?`) | Currently `.lower() + substring`, no regex — but worth pinning | `test_search_with_regex_metachars_is_literal` |
| T5 | Non-ASCII filenames / Korean titles (related: B6) | Project default locale=ko | `test_write_and_search_korean_title` |
| T6 | e2e for write→search round-trip via rendered harness.yaml | `test_second_brain_e2e.py` covers render→load but not write→search | `test_e2e_write_then_search_via_rendered_config` |
| T7 | wrapup template integration (related: I1) | The integration UX gap is invisible without an e2e test that simulates wrapup writing | `test_wrapup_template_can_write_note_with_minimal_frontmatter` — would FAIL today; that is the point |
| T8 | `vault_path` portability across OS (related: B3/D2) | WSL path drift is silent | `test_default_production_harness_yaml_vault_path_uses_placeholder` |

## Devils-advocate self-critique

Per ADR-002 amended, 7-item checklist gate:

1. ✅ **Live exercise produced an observation contradicting unit-test assumption** — three cascading validation errors (C1, C2 paragraph 1, C3 first finding) are exactly the friction surface that unit tests don't see because the test fixtures always supply correct schema from the start.
2. ✅ **All 6 dimensions traversed** — every section has at least 2 findings or an explicit `passes` info marker.
3. ✅ **Severity defensible** — I1 is critical because wrapup-side note-writing is automatic and the failure mode is silent. Major findings (C1/C3/C5/B3/D2/I2/I4/U1) all have either reproduction steps or specific code line citations. Minors are quality-of-life. Infos are observations / confirmations.
4. ✅ **No-finding sections have rationale** — none of the 6 sections is empty; the `info`-level entries with `(passes)` annotation document what was checked.
5. ✅ **All files in PLAN read scope covered** — `second_brain.py` end-to-end, `SecondBrainConfig`+`SecondBrainFolder`+`SecondBrainNoteType` in `models.py` L268-L367, `tests/unit/test_second_brain.py` 442 LOC fully, `tests/integration/test_second_brain_e2e.py` first 80 LOC (the integration shape is the load-time contract — write-time is covered by unit tests); 4 stage-template integration points in `templates/stages/*.md.j2`.
6. ✅ **Tests read, not just source** — see #5. Mock fixtures inspected for fidelity (B1).
7. ✅ **Error paths exercised** — path traversal, write outside folder, bad type, empty query, missing frontmatter all hit live.

**Self-critique adjustment:** initial draft had I1 as `major`. On re-read, I escalated to `critical` because wrapup is automatic — the LLM has no opportunity for trial-and-error, and silent-drop of intended writes is the load-bearing failure mode the user flagged at PLAN time ("mock 위주라 신뢰 X"). Body finalized with I1 = critical.

## Cross-references

- [[PLAN-untested-trio-review-2026-05-19]] — parent plan (this REVIEW = Phase 1 deliverable)
- [[PLAN-second-brain-write-failure]] — prior plan that resolved the fixture-vs-production gap (B1 documents the success)
- [[REVIEW-refdocs-2026-05-19]] — sibling REVIEW (Phase 2; check for shared validator-message-clarity pattern in U1/C2)
- [[REVIEW-sibling-repo-2026-05-19]] — sibling REVIEW (Phase 3)
- [[REVIEW-untested-trio-summary-2026-05-19]] — Phase 4 cross-cutting summary
