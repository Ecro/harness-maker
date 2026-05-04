---
generated_by: harness-maker
harness_maker_version: 0.4.4
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/verify-before-completion/SKILL.md.j2
provenance: official
name: verify-before-completion
description: Pre-wrapup gate enforcing 6 checks before any /hm:wrapup or autoloop
  iteration close. Failure on any check blocks completion and surfaces the failing
  check name + remediation hint.
content_hash: c28985a37c6edbd99c91da68511cee45c15ff491baa597596b37c452479c56fd
---

# verify-before-completion

Mandatory gate that runs immediately before `/hm:wrapup` or before an
autoloop iteration is considered closed. All 6 checks must pass; the first
failure short-circuits the gate and blocks completion.

## When to Invoke

- `/hm:wrapup` — automatically before commit
- `/hm:loop` — at the end of each iteration
- Manual: `/hm:verify`

## The 6 Checks

### 1. PLAN/SPEC fulfillment — LLM-judged (hard fail)

LLM reads the PLAN body + diff and rules each item `fulfilled` or not with
cited evidence. Ticked checkboxes alone do NOT pass — the diff must contain
matching code/test/doc changes.

```bash
work_docs="work-docs/"
test -d "$work_docs" && grep -rq "PLAN-" "$work_docs" || exit 1
plan=$(ls "$work_docs"/PLAN-*.md 2>/dev/null | head -1)
test -n "$plan" || exit 1
diff_file=$(mktemp)
trap 'rm -f "$diff_file"' EXIT
git diff HEAD~1 HEAD > "$diff_file" 2>/dev/null || git diff > "$diff_file"
PLAN="$plan" DIFF_FILE="$diff_file" \
  uv run --with /home/noel/harness-maker python -c "
import os, sys
from pathlib import Path
from harness_maker.llm_judge import AnthropicJudgeClient
from harness_maker.plan_verify import PlanVerifyError, verify_plan
diff_text = Path(os.environ['DIFF_FILE']).read_text(encoding='utf-8', errors='replace')
try:
    result = verify_plan(Path(os.environ['PLAN']), diff_text, client=AnthropicJudgeClient())
except PlanVerifyError as e:
    print(f'BLOCKED: PLAN verify error — {e}', file=sys.stderr); sys.exit(1)
if not result.overall_pass:
    for it in (i for i in result.items if not i.fulfilled):
        print(f'BLOCKED: {it.text} — {it.reason}', file=sys.stderr)
    sys.exit(1)
"
```

### 2. Regression / smoke gate

```bash
bash .claude-verify.sh phase_${CURRENT_PHASE} || exit 1
```

### 3. Health score within −5 of baseline

```bash
uv run --with /home/noel/harness-maker python -c "
from pathlib import Path
from harness_maker.readiness import compute_health
from harness_maker.models import Preset
import json, sys
score = compute_health(Path('.'), Preset.SIDE)['composite']
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

First failing check halts the gate. Output: `BLOCKED: check <N> (<name>) — <stderr tail>`.
When blocked, the calling command must abort. Remediation hints:
PLAN unclosed → list incomplete tasks; smoke fail → re-run failing test;
Health drop → show 6-dim breakdown; pending refresh → `/hm:refresh`;
security high → list findings; merge conflict → show conflicting paths.

<!-- @hm:user:extensions -->
<!-- Project-specific verify checks beyond the 6 baseline. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
