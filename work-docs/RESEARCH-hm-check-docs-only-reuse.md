---
type: research
task_slug: hm-check-docs-only-reuse
status: complete
created: 2026-11-02
tags: [hm-check, reuse, verdict-record, test-selection, wrapup-cost]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://docs.python.org/3/library/audit_events.html
  - https://pypi.org/project/pytest-testmon/0.9.16
  - src/harness_maker/check.py
  - src/harness_maker/test_dep_map.py
  - src/harness_maker/templates/stages/wrapup.md.j2
  - workdesk@aec64b8 full gate with an audit-hook read-set plugin (2026-11-02, n=1)
  - /tmp/claude-1000/-home-noel-workdesk/6b27d8ad-f654-46ba-836c-d26d0081fc40/scratchpad/harness-maker-ask.md
related_docs:
  - work-docs/PLAN-hm-cost-p3.md
  - work-docs/RESEARCH-hm-cost-p3.md
  - specs/SPEC-hm-cost-p3.md
summary: Per-section reuse + DRI-declared inert globs, verified against the recorded read-set
---

# RESEARCH — hm-check-docs-only-reuse

## Recommended Direction

Measured on workdesk (below): automatic test selection is not viable there. 98% of gate
time is in test files that spawn subprocesses, and session-scoped fixtures spawn `git`,
`node`, `uv` and `python`. Neither a grep rule nor a recorded read-set can prove that a
document edit is irrelevant. What is left, and is cheap:

1. **Reuse per section, not per verdict.** Recompute `approval`, `ac`, `review`, `security`
   and `cve` on every run; they are fast and they are what reads documents and HEAD. Key only
   the gate results. A REVIEW-table fix then reruns `review_section`, which it *must* reread,
   and not the 33-minute pytest.
2. **Leave DRI-declared inert globs out of the gate key** (e.g. `check.reuse_inert`, default
   **empty**). The gate is reused when every path in the delta from the stored snapshot
   matches an inert glob. Any other path, an added or removed path, a HEAD change, a missing
   record or any doubt reruns the full gate.
3. **Check the declaration against what tests actually read.** Every gate pytest run carries
   a small PEP 578 plugin that records the in-repo paths opened in-process. A declared-inert
   path that was read voids the declaration for that path, and the receipt names it. This
   catches what it can see (in-process reads; workdesk reads
   `work-docs/RESEARCH-workdesk-design-improvements.md` this way). Subprocess reads remain
   the declared risk, and the receipt says so.

Reason: the ask's "no changed path is `is_code_or_test`" predicate is a denylist of code. It
calls `.sql`, `.ps1`, `.css`, `.html`, `.json` and `.yaml` documents
(`CODE_SUFFIXES`, `check.py:37-53`). In workdesk those are migrations, the collector and the
web UI, and tests read them. "Docs-only" has to be an allowlist the DRI owns.

## Measurement (workdesk, 2026-11-02, n=1)

Setup: workdesk@aec64b8, `.venv/bin/python -m pytest -p hm_readset -p no:cacheprovider
--junitxml=…`. The throwaway plugin records `open`/`os.listdir`/`os.scandir` per test file,
and `subprocess.Popen`/`os.system`/`os.posix_spawn`/`os.exec`/`os.spawn`. Reads at
collection time or during non-function-scoped fixture setup count as *global*. Scripts:
`/tmp/claude-1000/-home-noel-harness-maker/79356289-9a11-46d7-90b9-32b2c906d8e7/scratchpad/readset/{hm_readset.py,analyse.py}`.

| Fact | Value |
|---|---|
| Result | `2053 passed, 1 warning in 2053.15s (0:34:13)`, rc=0 |
| Test files / audited events | 88 / 32,633 |
| Files that spawn a subprocess | 83 of 88 (94%), **98% of junit time** |
| Spawns from scoped fixtures (global taint) | python, git, node, powershell.exe, tar, uv, wslpath (65 calls) |
| Global (collection/scoped) non-code reads | 61, incl. `docs/DESIGN.md` and every `specs/*.golden.json` |
| Rule-B rerun fraction per tracked non-code path (1305 paths) | median 100%, min 100% |
| In-process reads under `work-docs/` / `CHANGELOG*` / `.claude/` | 1 (`work-docs/RESEARCH-workdesk-design-improvements.md`) / 0 / 0 |
| Directories listed under `work-docs/` | 41 `work-docs/shots-*` screenshot dirs plus `work-docs` itself |
| Hook overhead | 2053 s vs the ask's 33 min (≈1980 s, 1986 tests): within noise, and the test count differs (2053) |

Inference: B is all-or-nothing in workdesk, because the global subprocess taint alone forces
the full gate on every delta. The in-process read-set is still useful as a *check* on a
declaration (point 3), and it costs nothing measurable.

## Approaches Found

### A. Grep selection (the ask's proposal) — rejected

- **Assumption:** a test that reads a document names its path or basename.
- **Against:** fact, workdesk: `specs/*.golden.json` is loaded at collection by glob (global
  reads above). `tests/test_s1_collector.py` reads `collector/{event_write,spool,teams}.ps1`,
  and `tests/test_s0_quick.py` reads `quick/{idle,install}.ps1`, without either source naming
  the path or the basename (analyse.py "grep-rule misses"). The other entries in that list
  are relative opens inside a fixture git dir: noise. This repo: 55 test files glob `*.md`.
  `test_dep_map.py:666-670` records the same false green for its hand-made inert list.
- Risk: **high**. Its failure looks the same as a clean pass.

### B. Automatic selection from a recorded read-set — not viable for workdesk

- **Assumption:** what a test file read in its last pass bounds what it depends on.
- **For:** PEP 578 raises `open`, `os.listdir`, `os.scandir` and `subprocess.Popen`
  (docs.python.org/3/library/audit_events.html). It sees glob reads.
- **Against:** measured. 98% of time is subprocess-tainted, and the scoped-fixture taint is
  global, so every delta reruns everything. There is no `stat` audit event: presence checks
  are invisible. Fixture and cache reads are attributed to whoever paid them first.
- Fit: it might help a pure in-process Python suite (this repo's? unmeasured). Building it
  for a hypothetical project contradicts the 제1목표 (simple over complex). Risk: medium,
  benefit ≈0 where it was asked for.

### C. Per-section reuse (recommended, part 1)

- **For:** fact: one key covers `head` and every digest (`check.py:1182-1208`), and `_reused`
  returns the whole old `line` (`check.py:1211-1225`). Yet `ac` and `security` read
  `changed_paths()` = `git diff HEAD` (`check.py:202-215`, `690`, `899-905`), `review` reads
  `REVIEW-<slug>-*.md` (`check.py:836-850`) and `approval` reads the SPEC. All are fast.
  Only `gates_section` runs commands (`check.py:332-349`).
- **The ask's HEAD question:** **no**, a tree-equal HEAD change does not reuse today, because
  `head` is its own key field. Dropping HEAD from the *whole* verdict would be wrong. After the
  wrapup commit, `changed_paths` is empty, so `ac`'s skip-path branch and `security`'s
  gating set change meaning. Under C those are recomputed anyway. Whether HEAD can leave the
  *gate* key is the open question: workdesk's scoped fixtures run `git`, so independence from
  HEAD can't be proven.
- Risk: **low**. Alone it does not avoid the measured reruns: the REVIEW digest still
  changes the gate key. It needs D.

### D. DRI-declared inert globs, verified (recommended, part 2)

- **Assumption:** the DRI knows which paths the gate cannot depend on, e.g. `CHANGELOG.md`,
  `work-docs/PLAN-*.md`, `work-docs/REVIEW-*.md`, `.claude/memory/**`.
- **For:** the simplest rule that hits all three measured reruns: a docs edit, a REVIEW-table
  fix (with C), and a docs-only rebase (only if HEAD leaves the gate key).
- **Against:** a hand list. `test_dep_map.py:684-686` shows one going asymmetric.
  The measurement shows a harness-owned default would be wrong: workdesk reads a
  `work-docs/RESEARCH-*` file in-process. So the default stays empty, and the in-process
  read-set check (point 3) voids a declared path that was read.
  Subprocess reads stay unverified, and the receipt says so.
- Fit: the key builder already takes `config` (`check.py:1182`). The new parts are the
  per-path snapshot stored with the record, a glob match over the delta, and the plugin on the
  existing `_is_pytest` branch (`check.py:338-340`). Risk: **medium**. It is a DRI
  declaration, partly checked.

### Out of scope, and larger: parallelise the gate

A serial 34-minute pytest is the cost that reuse works around. `-n auto --dist loadfile`
cuts every run, cold ones included. Workdesk already has a `.worktrees/test-suite-speed`
task (seen 2026-11-02, contents not read). That is the consumer's choice, not `hm check`'s.

## Pitfalls

- **`is_code_or_test` is not a "safe to skip" predicate.** It was written for the AC
  skip-path and misses `.sql`, `.ps1`, `.css`, `.html`, `.json`, `.yaml` and `.toml`
  (`check.py:37-53`). Workdesk has 28 `.sql`, 8 `.ps1`, 12 `.html` and 2 `.css` tracked.
- **A false green looks like a pass.** A reused or partly reused verdict must name its rule,
  the delta and the excluded paths in the receipt (`test_dep_map.py:694-700`, "the strongest
  possible false green").
- **Added or removed paths** are invisible to presence checks and change directory listings
  (workdesk lists `work-docs/shots-*`). They rerun the full gate even when they match an inert
  glob.
- **The record stays fail-closed** as today. Write it only on exit 0, with no `unreadable:*`,
  HEAD unmoved and the plugin output present; unlink it on any non-zero run
  (`check.py:1288-1296`). A missing plugin output means no read-set check, so do not reuse.
- **Dogfood self-reference:** a worktree edit to `check.py` changes the gate. Today the
  tree digest covers it. Keep `src/harness_maker/check.py` out of any declared glob by
  construction (it is `.py`, so the inert match must never be able to accept code suffixes).
- **CVE:** `cve_section` runs fresh under C, which removes the stale-lookup caveat of today's
  reuse (wiki `hm-check-reuse-verdict-record`).

## Open Questions

1. **HEAD in the gate key.** Keep HEAD (fail-closed; the docs-only rebase case still reruns),
   or let the DRI declare `reuse_across_head`? Workdesk spawns `git` from scoped fixtures,
   so independence from HEAD can't be measured, only declared.
2. **Is the read-set check worth its plugin**, given that it sees only in-process reads (it
   found one real conflict in workdesk)? The alternative is a declaration with no check,
   simpler and blind.
3. **Do non-pytest gates rerun on an inert-only delta?** Recommended: no. The same declaration
   covers every gate, because `mechanical_checks` can be slow and the DRI declared the paths
   irrelevant. The SPEC decides.
4. **Receipt shape** for `reused: {rule, delta, inert_matched, voided, unverified:
   "subprocess"}`, and the one line `/hm:wrapup` Step 1 prints.
5. **Where the declaration lives:** `harness.yaml` (rendered and preserved across
   `/hm:make`) versus a project-owned file. `harness.yaml` is already in the key.

## Sources

- docs.python.org: [Audit events table](https://docs.python.org/3/library/audit_events.html).
  `open`, `os.listdir`, `os.scandir` and `subprocess.Popen` are raised. There is no `stat`
  event.
- pytest-testmon on [PyPI](https://pypi.org/project/pytest-testmon/0.9.16). Prior art: data
  files (txt, xml, assets) are a change category it does not track, and it suggests declaring
  them by hand. That is the same conclusion D reaches.
- `src/harness_maker/check.py:37-53` (CODE_SUFFIXES), `:173-220` (snapshot, changed set,
  `is_code_or_test`), `:332-349` (gates), `:836-850` (review), `:1182-1296` (key, reuse,
  record, unlink).
- `src/harness_maker/test_dep_map.py:660-700`: the hand-curated selector and its recorded
  false greens. It is specific to harness-maker and not used by any template.
- `src/harness_maker/templates/stages/wrapup.md.j2:21`: Step 1 is the only `--reuse` caller.
- The workdesk measurement above, and the ask (1986 tests, 33 min, 3 reruns in one wrapup).

## Related Internal Docs

- `work-docs/PLAN-hm-cost-p3.md`, `specs/SPEC-hm-cost-p3.md`: origin of `--reuse` and ADR-001
  (reuse lives in `run`, not in `Options`).
- `work-docs/RESEARCH-hm-cost-p3.md:75-79`: wrapup −9%, "a reused gate saves test wall time,
  not tokens". The same holds here.
- wiki `[wiki:architecture] hm-check-reuse-verdict-record`: the current record's fail-closed
  rules.
