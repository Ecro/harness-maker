---
generated_by: harness-maker
harness_maker_version: 0.20.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/verify-before-completion/SKILL.md.j2
provenance: official
name: verify-before-completion
description: Pre-wrapup gate enforcing 6 checks before any /hm:wrapup or autoloop
  iteration close. Failure on any check blocks completion and surfaces the failing
  check name + remediation hint.
content_hash: a34a1e7064e17d85aaf3a90ab05e761e066a4b48d99a1a404eb5f88a4e491f55
---

# verify-before-completion

Mandatory gate before `/hm:wrapup` or autoloop iteration close. All 6
checks must pass; the first failure short-circuits and blocks.

Invoke before `/hm:wrapup` (M8 invariant), at the end of every `/hm:loop`
iteration, or on demand via `/hm:verify`. Skip only for trivial work units
(typo / docs-only / config-only — wrapup's pre-flight covers it) or when a
previous PASS in the same session is still valid (no new commits / test
changes since).

## The 6 Checks

### 1. PLAN/SPEC fulfillment — you verify (hard fail)

You are the judge for this check. Do NOT delegate to a subprocess.

```bash
work_docs="work-docs/"
test -d "$work_docs" || { echo "BLOCKED: check 1 — work_docs dir missing"; exit 1; }
plan=$(ls "$work_docs"/PLAN-*.md 2>/dev/null | head -1)
test -n "$plan" || { echo "BLOCKED: check 1 — no PLAN-*.md found"; exit 1; }
echo "PLAN=$plan"
!git diff HEAD~1 HEAD 2>/dev/null || git diff
```

Read the PLAN file (`$plan`) and the diff. For each numbered item, task,
or acceptance criterion the diff must contain matching code/test/doc
changes — a ticked checkbox alone does NOT pass. On any miss, output
`BLOCKED: check 1 (PLAN-fulfillment) — <item text> not found in diff` and
stop (do not proceed to check 2).

### 2. Regression / smoke gate

```bash
bash .claude-verify.sh phase_${CURRENT_PHASE} || exit 1
```

### 3. Health score within −5 of baseline

```bash
uv run --with /home/noel/harness-maker python -c "
from pathlib import Path
from harness_maker.readiness import compute_readiness
from harness_maker.models import Preset
import json, sys
result = compute_readiness(Path('.'), Preset('Production'))
score = result.composite
metrics = Path('.claude/observability/metrics.jsonl')
baseline = 0
if metrics.exists():
    for line in metrics.read_text().splitlines():
        rec = json.loads(line)
        if 'health' in rec: baseline = rec['health']
sys.exit(0 if score >= baseline - 5 else 1)
"
```

### 4. Anti-rot pending resolved

```bash
test ! -f .claude/observability/refresh/pending.jsonl || \
  grep -q '"action":"defer"' .claude/observability/refresh/pending.jsonl || exit 1
```

### 5. Zero high-severity security findings

```bash
findings=.claude/observability/security/findings.jsonl
if [ -f "$findings" ]; then
  count=$(grep -c '"severity":"high"' "$findings" || true)
  [ "$count" -eq 0 ] || exit 1
fi
```

### 6. Worktree merge-safe

```bash
git diff --check || exit 1
git merge-tree $(git merge-base HEAD main) HEAD main | grep -q "<<<<<<<" && exit 1
exit 0
```

## Failure Behavior

First failing check halts the gate.
Output: `BLOCKED: check <N> (<name>) — <reason>`.
When blocked, the calling command must abort. Remediation hints:
PLAN unclosed → list incomplete tasks; smoke fail → re-run failing test;
Health drop → show 6-dim breakdown; pending refresh → `/hm:refresh`;
security high → list findings; merge conflict → show conflicting paths.

<!-- @hm:user:extensions -->
<!-- Project-specific verify checks beyond the 6 baseline. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
