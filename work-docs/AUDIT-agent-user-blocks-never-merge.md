# BUG: `.claude/agents/*.md` user blocks never merge — 13 of 15 agents freeze on first edit

**Severity:** P1 — a shipped feature (`@hm:user:extensions` in agent templates) is
inert for every affected file, and the failure mode is silent.
**Affects:** 13 of 15 agents. `.codex/agents/*.toml` are unaffected.
**Found:** 2026-08-20, harness-maker 0.52.6, verified by controlled experiment.
**Reporter:** spoton project.

---

## Summary

Every agent template ships a `<!-- @hm:user:extensions -->` block, documented as
*"Preserved across harness-maker upgrades."* That preservation never happens.

Once a user writes anything into that block, the file's `content_hash` stops
matching, reconcile takes the hash-mismatch branch, and `_decide_user_modified()`
looks for markers in the **wrong file** — the outer `agents/<name>.md.j2`, which is
a 10-line frontmatter shim. The markers live in `agents/<name>_body.md.j2`, reached
via `{% include %}`. `has_markers()` does not follow includes, so it returns False
and the decision falls through to `KEEP, "hash-mismatch-user-modified"`.

Net effect: **the file freezes permanently and silently.** It keeps the user's
content and stops receiving every future template improvement. The user gets no
warning, and the only visible symptom is that an agent quietly stays on an old
prompt across upgrades.

This is the exact scenario the block-merge feature exists to prevent.

---

## Root cause

`src/harness_maker/reconcile.py`, `_decide_user_modified()` (~line 369):

```python
def _decide_user_modified(template_name: str, old_body: bytes) -> tuple[ReconcileDecision, str]:
    template_path = _TEMPLATE_DIR / template_name        # agents/code-reviewer.md.j2
    template_src = template_path.read_text(encoding="utf-8")
    ...
    if has_markers(template_src) and has_markers(old_text):   # ← template_src has NO markers
        return ReconcileDecision.MERGE_BLOCK, "hash-mismatch-mergeable"
    return ReconcileDecision.KEEP, "hash-mismatch-user-modified"   # ← always taken
```

`agents/code-reviewer.md.j2` in full:

```jinja
---
name: code-reviewer
communication_variant: reframe
description: Reviews code changes for correctness, readability, maintainability, and basic security/performance hygiene
tools: Read, Grep, Glob
{% include "agents/_partials/model_frontmatter_line.md.j2" %}
review_scope: [code]
---

{% include "agents/code-reviewer_body.md.j2" -%}
```

The marker is at `agents/code-reviewer_body.md.j2:62`.

Measured with the shipped helper:

```
has_markers()   template
─────────────   ────────────────────────────────────────
    False       agents/code-reviewer.md.j2          ← what reconcile reads
    True        agents/code-reviewer_body.md.j2     ← where the marker is
    False       agents/concurrency-reviewer.md.j2
    False       agents/performance-reviewer.md.j2
```

---

## Scope

Outer templates with zero markers whose literal `{% include %}` targets have them:

```
agents/autoloop-coder.md.j2          agents/security-auditor.md.j2
agents/code-reviewer.md.j2           agents/security-reviewer.md.j2
agents/code-verifier.md.j2           agents/stuck.md.j2
agents/concurrency-reviewer.md.j2    agents/test-reviewer.md.j2
agents/consensus-arbiter.md.j2       agents/ux-reviewer.md.j2
agents/executor.md.j2
agents/performance-reviewer.md.j2
agents/plan-validator.md.j2
```

13 of 15. The other two — `judgment-reviewer`, `stage-delegate` — carry no user
markers at all in either file, so they are out of scope here (possibly a separate
gap: they offer users no extension point).

**Control group:** `.codex/agents/*.toml` render from a single-file template
(`codex/agent.toml.j2`) with the marker inline. All 16 merge correctly on the same
run. That is what confirms the split-template structure is the discriminating
variable, not the marker syntax or the merge machinery.

`skills/`, `stages/`, `commands/` were scanned with the same predicate — none
affected.

---

## Reproduction

Verified end to end on a real project (spoton, 0.52.6):

```bash
# 1. Start from a cleanly rendered agent file (hash matches).
rm .claude/agents/code-reviewer.md
harness-maker make --update .
grep -c '^content_hash:' .claude/agents/code-reviewer.md      # → 1

# 2. Write into the user block (the documented supported action).
#    …insert text between @hm:user:extensions markers…

# 3. Poison the TEMPLATE region, outside the user block.
sed -i 's|- UI / a11y → defer to ux-reviewer|&  ZZPOISONZZ|' .claude/agents/code-reviewer.md

# 4. Re-render.
harness-maker make --update .

# 5. Check.
grep -c ZZPOISONZZ .claude/agents/code-reviewer.md
#   expected (MERGE_BLOCK): 0 — template region restored, user block preserved
#   actual   (KEEP):        1 — whole file frozen
```

**Observed: 1.** The re-render log lists 20 `MERGE_BLOCK:` lines, all
`.codex/agents/*.toml` plus `AGENTS.md` / `memory/*`. No `.claude/agents/*.md`
appears in that list on any run.

Note that step 3 is what makes this conclusive. Without it the file's bytes are
unchanged across the re-render and KEEP is indistinguishable from a successful
merge — which is presumably why this has gone unnoticed.

---

## Suggested fix

Make the marker probe follow literal `{% include %}` targets. A static scan is
sufficient — no Jinja evaluation, no context needed:

```python
_INCLUDE_RE = re.compile(r'{%-?\s*include\s+"([^"]+)"')

def _template_has_markers(template_name: str, _seen: frozenset[str] = frozenset()) -> bool:
    """has_markers() over a template and its literal includes.

    Agent templates are split: the outer .md.j2 is a frontmatter shim whose only
    body is `{% include "<name>_body.md.j2" %}`, and the @hm:user markers live in
    the body. Probing only the outer file reports False and freezes the file.
    """
    if template_name in _seen:
        return False
    try:
        src = (_TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    except OSError:
        return False
    if has_markers(src):
        return True
    seen = _seen | {template_name}
    return any(_template_has_markers(inc, seen) for inc in _INCLUDE_RE.findall(src))
```

then in `_decide_user_modified`:

```python
-    if has_markers(template_src) and has_markers(old_text):
+    if _template_has_markers(template_name) and has_markers(old_text):
```

`template_src` is still needed for the `OSError → hash-mismatch-template-unreadable`
branch, so keep that read.

**On dynamic includes.** `_body` templates contain
`{% include "agents/_standards/" + d + ".md.j2" ignore missing %}`, which a static
regex cannot resolve. That is fine here: no file under `agents/_partials/` or
`agents/_standards/` contains a user marker (verified), so literal-only recursion
finds every marker that exists. If a domain pack ever adds one, the recursion
degrades to today's behaviour for that file rather than misbehaving.

**Alternative considered:** pass the rendered new body into `_decide_user_modified`
instead of re-reading the template. More robust in principle — it sees exactly the
bytes that would be written — but reconcile currently runs over the blueprint
before render, so it would mean either rendering twice or restructuring the
pipeline. The static scan is the smaller change and covers the observed failure.

---

## Suggested regression test

The bug survived because the outer template's *absence* of a marker is invisible
from the rendered output — the rendered file has the marker, so any test asserting
on rendered bytes passes. Assert on the decision instead:

```python
def test_agent_user_block_merges_not_keeps(tmp_path):
    """Split-template agents must reach MERGE_BLOCK, not KEEP, after a user edit.

    Regression: has_markers() probed the outer .md.j2 (a frontmatter shim) rather
    than the _body.md.j2 that holds the markers, so all 13 split agents froze on
    first user edit.
    """
    for name in ("code-reviewer", "concurrency-reviewer", "performance-reviewer"):
        decision, reason = _decide_user_modified(
            f"agents/{name}.md.j2",
            edited_body_bytes(name),      # rendered output + text inside the user block
        )
        assert decision is ReconcileDecision.MERGE_BLOCK, (name, reason)
```

A cheaper structural guard, as a companion: for every blueprint template, assert
that if any literal include target has markers, the reconcile probe reports True.
That catches the next template that gets split.

---

## Impact seen in the field

In spoton this compounded with a second issue. Three agents predated their
harness-maker templates and had no `content_hash` at all, so they were classified
`KEEP, "frontmatter-no-hash-not-ours"` — correct behaviour, user files.

But `/hm:review` dispatches by *name*: four core lenses as
`subagent_type="code-reviewer"`, plus `concurrency-reviewer` as a mandatory lens
(`harness.yaml` marks design/functionality/robustness/consistency/security/
concurrency/tests as running every round regardless of routing). Claude Code
resolves those names to `.claude/agents/*.md`. So the harness dispatched its own
mandatory lenses through files it did not own and could not update — for three
months. The concurrency lens was still running a prompt that described a thread
model with two symbols that no longer exist in the codebase.

We fixed that by deleting the three files, re-rendering, and moving the
project-specific content into the user blocks — which is the documented path. Then
this bug froze them again on the very next edit.

The two failure modes have different fixes:

| | cause | fix owner |
|---|---|---|
| no `content_hash` | pre-existing user file with a colliding name | project (delete + re-render) |
| **markers not found** | **reconcile probes the wrong template** | **harness-maker** |

Worth considering separately: `/hm:health` currently has no check for *"an agent
this harness dispatches by name that reconcile will never update."* Both failure
modes above are invisible until someone diffs a rendered file against its template
by hand.
