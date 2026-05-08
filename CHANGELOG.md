# Changelog

## 0.7.1 — 2026-05-08

Patch release closing all P1 + P2 carry-overs from
`REVIEW-harness-gap-cot-2026-05-2026-05-08.md` and
`REVIEW-harness-gap-cot-wiring-2026-05-08.md`. No new features; no
architectural changes; no breaking API changes.

> **Note on version sequencing:** the marketplace stamps had remained at
> 0.6.2 even though the 0.7.0 wiring round (commits 52346c9 → 00d91a0 →
> 3c7304a) was complete on `main`. This release coalesces that internal
> 0.7.0 work + this 0.7.1 cleanup into a single marketplace-published
> 0.7.1 — there is no separate published 0.7.0 artifact.

### Closed REVIEW findings

#### Security
- **Sec-R2-3 (P1)** — `telemetry.py` cwd resolution now uses env-var
  precedence (`CLAUDE_PROJECT_DIR` → `CURSOR_PROJECT_DIR` → stdin
  `workspace.current_dir` → `os.getcwd`). The bare stdin `cwd` field is
  no longer consulted; a poisoned PostToolUse payload can no longer
  redirect metric writes to an attacker-chosen path. (ADR-102)
- **Sec-R2-6 (P1)** — `_load_recent_tool_calls` now reads structured
  `tool_input` whose schema is enforced at write time (whitelist
  projection); upstream poisoning paths are narrowed.
- **Sec F6 parent (P1)** — `DriftMonitor.score` wraps both baseline and
  current text in XML fences with an instruction preamble before
  passing to the LLM judge; embedded `</baseline>` / `</current>`
  close-tags are escaped so an adversarial SPEC body cannot inject
  instructions. (ADR-108)
- **Sec F7 parent (P1)** — `secscan.hallucination._is_available` no
  longer calls `importlib.util.find_spec`; uses a pure filesystem scan
  of `sys.path` so the hallucination gate cannot be coerced into
  executing `__init__.py` or `.pth`-registered finder side effects.
  (ADR-105)
- **Sec F7 R2 (P2)** — `tool_input` strings are scrubbed by
  `_SECRET_PATTERNS` (`sk-…`, `ghp_…`, `AKIA…`, `Bearer …`) before the
  256-char value cap, so a partial-secret tail cannot survive
  truncation. (ADR-107)

#### Concurrency / data integrity
- **Conc-R2-2 (P1)** — Documented the lock-free read contract on
  `SemanticStore.read_all` / `search` and `ProfileStore.get` /
  `get_all`: `os.replace` atomicity guarantees readers see either the
  pre- or post-write file in full, but a read concurrent with a write
  may return the pre-write snapshot. (ADR-104)
- **Code F1 (P1, latent)** — `exclusive_lock` is now re-entrant within a
  single thread via a `threading.local` depth counter keyed by lock
  path string. Same thread can acquire the same lock twice without
  deadlock. (ADR-106)

#### Performance
- **Perf-R2-1 (P1)** — `metrics.jsonl` now rotates per-day to
  `metrics-YYYY-MM-DD.jsonl`; the legacy filename remains readable as a
  compat fallback. New shared reader `harness_maker._metrics_io.iter_recent_entries`
  walks dated files newest-first; both `cache_diagnostics.diagnose_cache`
  and `security_scanner._load_recent_tool_calls` use it (no more
  full-file `read_text().splitlines()`). (ADR-103)
- **Perf F5 (P2)** — `prod_name_guard.scan_sequence` switched to a
  `collections.deque(maxlen=window)` sliding-window walk; per-call cost
  dropped from O(n × window) to O(window).
- **Perf F6 (P2)** — `SemanticStore.write_many` bulk helper acquires
  the lock once for N entries instead of N times via repeated `write`.
- **Perf F7 (P2)** — `EpisodicStore.read_all(max_days=30)` defaults to
  the 30 most recent daily files; pass `None` for the pre-0.7.1
  unbounded behaviour.
- **Perf PF4 (P1, parent)** — `_is_available` now memoises via
  `functools.lru_cache(maxsize=512)`.

#### Code quality
- **Code F2 (P1)** — `security_scanner.scan_all` docstring updated from
  "5 gates" to "7 gates" (matches actual gate count since 0.7.0).
- **Code F3 (P1)** — `two_pass_review.merge_passes` now requires Pass-2
  entries to carry at least one `severity` key; otherwise treats Pass 2
  as failed and falls back to Pass 1, guarding against a malformed
  `[{}]` LLM response silently dropping all findings.
- **Code F7 (P2)** — `secscan.hallucination` now walks `except`
  handler bodies when collecting `guarded_lines`; the fallback import
  in `try/except ImportError: import alt` is now correctly tagged P2
  (guarded) instead of P0.
- **Code F8 (P2)** — `cache_diagnostics` zero-token skip uses
  `(parsed.get(field) or 0) == 0` so JSON `null` values also trigger
  the skip.

#### Tests
- 4 concurrency multiprocess tests bumped `p.join(timeout=30)` →
  `timeout=60` and added `assert not p.is_alive()` before the
  `exitcode` assertion to distinguish timeout from crash.
- New tests: `test_metrics_io.py` (6), `test_locking.py` (3), plus 6
  acceptance tests across telemetry / drift / hallucination /
  episodic / semantic for the items above.

### Out of scope (intentional carry-overs)

These remain on disk as documented limitations; promoted to the 0.8.0
plan if user feedback warrants:
- Sec F2 / F5 (parent) — `security_scanner._persist` and
  `telemetry` JSONL persistence still use plain `open("a")`. Treated as
  a deliberate hot-path exception; documented in code.
- SQLite migration for `semantic` / `profile` (rejected ADR-104).
- LOCK_SH read-side locking (rejected ADR-104).
- `find_spec` retention with `PYTHONNOUSERSITE` (rejected ADR-105).
- Schema versioning for metrics.jsonl entries — handled via
  forward-compatible field addition.
