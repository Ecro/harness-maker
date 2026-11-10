---
type: review
task_slug: root-unreadable-test
created: 2026-11-10
spec: "[[SPEC-root-unreadable-test]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: 1 nit (the patched path must be the resolved one), accepted and fixed."
---

# REVIEW — root-unreadable-test

One code-reviewer round with one nit; it was accepted and fixed, none is unresolved. The
cross-model second opinion is not configured for this harness. Only
`tests/unit/test_land_hold.py` changes; `src/` is untouched.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | nit | tests/unit/test_land_hold.py:467 | `compute_subject_hash` reads `(root / rel).resolve()`, so the patched `read_bytes` matched `bad` only while `tmp_path` held no symlink; otherwise the root row would fail "DID NOT RAISE". Fix: `bad` is the resolved path | accepted | SPEC AC-001 |

## Checked, no finding

- Non-root: `os.access(bad, os.R_OK)` is false, nothing is patched, and the row runs the real
  mode-000 read exactly as before.
- Root: `stat()` still succeeds, so the read reaches the patched `PermissionError`, which
  `compute_subject_hash` maps to `SubjectHashError` naming `s/bad.txt`.
- The patch passes every other path through and is undone by `monkeypatch` at teardown; the
  `finally` chmod restore still lets `tmp_path` be removed.

Caveat: as root the row exercises the `OSError` → `SubjectHashError` mapping with an injected
error, not a real permission failure. That is the AC's intent (the mapping, under any user).
