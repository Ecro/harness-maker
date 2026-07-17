---
type: review
task_slug: permission-deny-and-hooks-wiring
phase: "3+4"
status: CHANGES_REQUESTED
created: 2026-07-17
reviewers_invoked: [security-reviewer, codex]
consensus_method: cross-check (K=2 of N=2)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: permission-deny-and-hooks-wiring
  computed_at: 2026-07-17T11:30:00Z
human_review_needed: true
grade: D
---

# REVIEW — Phases 3 + 4 · **Grade D · DO NOT LAND**

## 🎯 Verdict

**Two consensus P0s. Both reviewers reached them independently.** Neither is auto-fixable:
each needs a design change, not an edit. Phases 3+4 must **not** be landed as they stand.

Phase 1 (`575c7bba`) and Phase 2 are unaffected and remain sound.

## ✅ Consensus P0 #1 — the retired `hooks.json` deletes user-authored hooks

`consensus-passed [2/2]` — **security-reviewer** (`synthesize.py:462`, P0) + **codex**
(`reconcile.py:563`, P1).

**The full traced sequence** (security-reviewer):

1. `synthesize.py:462` drops the `hooks/hooks.json` FileSpec (Phase 4).
2. `cli.py:483` calls `sweep_orphans(target, full_bp)` on every make/update.
3. `sweep_orphans` builds `expected` from `blueprint.files` (`reconcile.py:638`) — the path
   is no longer there, so it falls through to `_classify_orphan`.
4. The file is pure JSON with **no provenance frontmatter** (`render.py:11-15` strips it
   deliberately), so control reaches `reconcile.py:564`:
   `if current_hash in manifest.get(rel_key, set()): return ("ours-clean", current_hash)`.
5. `reconcile.py:653` unlinks it.

**Why that deletes the user's work:** `_render_hooks_json_merged` sets `fe.body_sha256` to
the **MERGED** file's hash (`render.py:847-849`). So a user who hand-wired a hook that
`_merge_hooks_json` preserved on their last `/harness-maker:make --update` has *that merged
hash* — their content included — recorded in `.hm-render-manifest.jsonl`. The bytes
hash-match → `ours-clean` → deleted. Reported as a routine sweep deletion, with **no**
`KEPT … manual review needed` warning.

codex, independently: *"Any user hook that was merged by an earlier render and then included
in the recorded merged-file hash is treated as harness-owned and deleted on the first render
after this change. This diff directly makes the path reachable by removing the FileSpec."*

Mitigation, not a fix: `cli.py:443` `backup(target_dotclaude)` copies `.claude/` to
`.backup-<ts>/` first, so the bytes are recoverable **if the user knows to look**.

**Fix (must be in the SAME commit as the FileSpec removal):** add
`.claude/hooks/hooks.json` to a `_SWEEP_NEVER_DELETE` set consulted at `reconcile.py:644`
before `_classify_orphan`, **and** implement ADR-005's pristine-exact-match delete in
`cli.py`. Do not ship Phase 4's render side alone — which is exactly what this diff does.

## ✅ Consensus P0 #2 — the `permission-surface-write` fix opened write bypasses

`consensus-passed [2/2]` — **security-reviewer** (`autopilot_guard.py:64`, P0) + **codex**
(`autopilot_guard.py:64`, P1).

The Phase-2 review found the rule blocked **reads** (`cat .claude/settings.json`). The fix
required a write token before the path. **It fixed the false positive and opened false
negatives.** These were blocked by the old bare-path regex and are **allowed now**:

```
python -c "open('.claude/settings.json','w').write('{}')"
perl -i -pe 's/deny/allow/' .claude/settings.json
git checkout HEAD -- .claude/settings.json
git restore .claude/settings.json
install /dev/null .claude/settings.json
printf '{}' | ex -sc 'wq' .claude/settings.json
```

**Why it is P0 and not a nit:** this is the *only* Bash-side rule protecting the permission
surface — `_git_segment_hit` (`:133-139`) blocks only push/reset --hard/stash drop, and
`NEVER_AUTO_WRITE_PATH` (`:76`) covers the Write/Edit tools only (`:274`). And **Phase 3
makes it live for the first time** (`settings/*.json.j2` wire `autopilot_guard` on
PreToolUse). So an autopilot-armed agent can rewrite `settings.json` — the file holding both
`permissions` and the `hooks` that gate it — through any interpreter. Privilege escalation,
newly reachable, shipped by the same diff that widened it.

**Fix (security-reviewer's, and it is the right shape):** invert the strategy. Do **not**
enumerate write tokens. Block any segment naming the surface **unless** it matches a narrow
read-only allowlist (`cat|less|head|tail|grep|jq|git diff|git log`, with the path not after
a `>`). A blacklist of write verbs is unbounded; the read set is small and closed.

## ⚠️ P1 — `>|` splits at the pipe, separating token from path

`manual-only` — **security-reviewer** (`autopilot_guard.py:87`).

`_SEGMENT_SPLIT = re.compile(r"[;&|\n]+")` splits before `NEVER_AUTO_BASH` is searched
per segment. Bash's noclobber-override `echo '{}' >| .claude/settings.json` becomes
`["echo '{}' >", " .claude/settings.json"]` — segment 1 has the token, segment 2 has the
path, neither matches. The old bare-path regex caught segment 2.

A one-character variation on the canonical `>` the rule exists to catch. **The P0 #2 fix
does not cover it** — pre-normalize `>|` → `>` (or split on `(?<![>])\|(?!\|)`) before
`_SEGMENT_SPLIT`.

## ⚠️ P2 — `spec_gate`'s matcher was mirrored on a FALSE premise

`manual-only` — **codex** (`Production.json.j2:81`).

I mirrored `hooks.json.j2:44`'s `Write|Edit` (dropping MultiEdit) and justified it as
"`Write|Edit|MultiEdit` would collide with the worktree_gate group (duplicate matcher =
duplicate `_entry_identity`)". **That reasoning is wrong.** `_entry_identity` keys on the
matcher **plus every command in the group**, so two groups sharing a matcher but differing
in commands have **different identities** and coexist fine.

So `spec_gate` can and should use `Write|Edit|MultiEdit`. What actually forced my hand was my
own over-strict `assert len(groups) == 1` per matcher — **a test assertion I wrote, then
treated as a constraint from the system.** The MultiEdit gap in spec-driven mode is real and
unnecessary.

## ⚠️ Manual-only — `Path.cwd()` in `_deny_dangerous_enabled`: reviewers DISAGREE

**Not bridged.** codex (P1, `permission_gate.py:141`): *"The subordination decision is rooted
at the hook process cwd instead of the project root from the payload/environment. A
subdirectory cwd silently turns every lookup into the fail-closed branch, defeating the
opt-out and adding a failed file lookup on every matched Bash call."*

security-reviewer explicitly **refuted** it: *"`Path.cwd()` reaching a DIFFERENT project's
harness.yaml would require Claude Code to invoke the hook outside the project root —
CLAUDE.md's Stop-hook note records cwd as the project root, and I found no code path or
payload field contradicting that. Flagging it would be speculation."*

Both takes stand. **Worth settling with a one-line probe** in the Phase-3 live check
(`pwd` from a PreToolUse hook in a subdirectory), since codex's failure mode is silent: the
flag becomes a no-op and every user gets unconditional blocking back.

## ✅ Cleared by review — do not re-litigate

- **`_deny_dangerous_enabled` cannot be flipped OFF by a malformed config.** Every
  non-mapping / parse-failure path returns True (`:99,:102,:107`); only a *readable* mapping
  with `permissions` absent (`:105`) or an explicit falsey value returns False — the
  documented 2026-05-31 default. `load_harness_yaml` skips the provenance doc **by content,
  not position**, so a truncated file cannot masquerade as key-absent. The unreadable-vs-
  absent-key split holds.
- **The ADR-007 producer-side split holds as designed.** `_SUBORDINATE_FLAG in sys.argv`
  (`:142`) is the only branch; the flag appears only in `templates/settings/*.j2`; the
  flag-absent default (`:125`) preserves the unconditional Cursor/Codex path.
  `test_codex_phase5` passes unmodified.
- **Both templates render valid JSON in both dev_modes.** The `{% if %}` places the leading
  comma inside the block and `permissions` closes independently — a dev_mode flip cannot
  take `permissions` down.
- **The YAML parse per Bash call is not the hot-path cost.** `load_harness_yaml` uses
  `safe_load_all` (no code exec); the `uv run --with` spawn dominates. Measure before
  optimising.

## 📝 Also open (P2)

- **The two newly-wired blocking gates ship without a `timeout`** (`Side.json.j2:29,36` +
  Production). `autopilot_guard`/`loop_gate` beside them have one. Add `"timeout": 10`.

## Grade

| | |
|---|---|
| P0 (consensus-passed) | **2** |
| P1 (consensus) | 0 |
| **Grade** | **D** |
| Threshold | A |
| Status | **CHANGES_REQUESTED** |
| human_review_needed | **true** |
| Auto-fix | **NOT attempted** — both P0s need a design change, not an edit, and rewriting a security rule on an exhausted context is the failure mode this session documented four times. |

## 🚧 What the next session must do, in order

1. **Do not land Phases 3+4.** Phase 1 (`575c7bba`) is landed and sound; Phase 2's code is
   sound (Grade A) but sits on the same branch.
2. **P0 #1** — land ADR-005's other half in ONE commit with the FileSpec removal:
   `_SWEEP_NEVER_DELETE` at `reconcile.py:644` + the pristine-exact-match delete in `cli.py`.
   Test: a `hooks.json` holding a user hook survives a sweep; a pristine one is deleted.
3. **P0 #2** — invert `permission-surface-write` to a read-only allowlist. Test both
   directions with the six bypass commands above **and** the read cases from
   `test_permission_surface_allows_reads`.
4. **P1** — normalize `>|` before `_SEGMENT_SPLIT`.
5. **P2** — `spec_gate` → `Write|Edit|MultiEdit`; drop the over-strict
   `assert len(groups) == 1` that forced the mirror; add `"timeout": 10` to both gates.
6. **Settle the `Path.cwd()` disagreement** with a probe in the Phase-3 live check.
7. **Then** re-review, and only then the live negative control (Phase 3's actual exit
   criterion, still undischarged).

## 🚧 Follow-ups (unchanged, still open)

1. `codex` second opinion is dead on the feature-branch path — the recipe resolves
   `.claude/schemas/…` relative to cwd, and `.claude/` does not exist in a task worktree.
   Worked around here with the base repo's absolute path; **without it this review loses the
   voter that produced both consensus P0s.**
2. `antigravity` never reads its prompt (2/2 this session). Production mandates it every
   review. Not invoked here.
3. Consensus filter cannot bridge severity tiers — `Path.cwd()` (codex P1 vs security
   refutation) and both P0s (P0 vs P1 across reviewers) all landed on one side of it.
4. wrapup destroys deliverables when `work-docs/` is gitignored — repo side fixed
   (`91e9de12`); the **stage** still has no guard.

## Note on voter pool

**N=2, so K=2 means unanimity.** A defect either reviewer missed could not reach consensus at
all. Both P0s were found by both — but the two P1-vs-P0 severity splits show how easily the
tier rule would have demoted them to `manual-only` had the reviewers rated them one tier
apart, which they nearly did.
