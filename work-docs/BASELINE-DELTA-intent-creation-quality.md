# Intent creation interview — surface delta

The intent-layer skill now requires a creator deep interview and proactive quality review. The SPEC creation path loads that shared procedure before writing an intent. Existing rendered-target and creation-contract tests validate integration; they do not prove interview quality in live use.

This change owns the regeneration under ADR-010: record all movements explicitly to avoid ratchet-rebaselined-by-its-own-subject. The aggregate grew; no command or round-trip count changed. The standalone intent-layer skill remains within the existing 120-line limit and is outside this command-surface aggregate.

| Variant / command | Frozen chars | Pre-edit live chars | New chars | Attribution |
|---|---:|---:|---:|---|
| claude / `configure` | 12082 | 12072 | 12072 | Pre-existing HEAD render drift; this task does not edit this command template. |
| claude / `execute` | 62670 | 62732 | 62732 | Pre-existing HEAD render drift; this task does not edit this command template. |
| claude / `help` | 2047 | 2043 | 2043 | Pre-existing HEAD render drift; this task does not edit this command template. |
| claude / `make` | 6626 | 6616 | 6616 | Pre-existing HEAD render drift; this task does not edit this command template. |
| claude / `review` | 87395 | 87419 | 87419 | Pre-existing HEAD render drift; this task does not edit this command template. |
| claude / `spec` | 47904 | 47778 | 48189 | SPEC delegates creator interview, quality review, body completion and readback to intent-layer. |
| claude / `verify` | 23898 | 23881 | 23881 | Pre-existing HEAD render drift; this task does not edit this command template. |
| claude / `wrapup` | 52539 | 52572 | 52572 | Pre-existing HEAD render drift; this task does not edit this command template. |
| codex / `hm-execute` | 61595 | 61657 | 61657 | Pre-existing HEAD render drift; this task does not edit this command template. |
| codex / `hm-help` | 2321 | 2317 | 2317 | Pre-existing HEAD render drift; this task does not edit this command template. |
| codex / `hm-review` | 83798 | 83822 | 83822 | Pre-existing HEAD render drift; this task does not edit this command template. |
| codex / `hm-spec` | 43586 | 43460 | 43871 | SPEC delegates creator interview, quality review, body completion and readback to intent-layer. |
| codex / `hm-verify` | 21260 | 21243 | 21243 | Pre-existing HEAD render drift; this task does not edit this command template. |
| codex / `hm-wrapup` | 50794 | 50827 | 50827 | Pre-existing HEAD render drift; this task does not edit this command template. |

New aggregate_chars: claude **402060**, codex **340488**.

`render_sha` is the generator-selected durable HEAD commit; `payload_digest` is regenerated from the measured surface. Pre-edit live values were measured with the HEAD SPEC template supplied through a temporary Jinja loader override, without modifying checkout files.

Manual procedure walkthroughs: a vague creation request waits for creator answers; a fully discussed intent reuses answers and confirms its synthesis; an accepted gap candidate still receives the interview; SPEC-derived drafts use the same procedure; status/metric recording do not trigger a creation interview.

A live creator interview subsequently rewrote `WORLD-INTENT-CLOSED-LOOP` with creator confirmation. It exposed a missing question-format constraint: the creator required concrete multiple-choice proposals, a recommended choice with rationale, and a free-text Other path. The skill now specifies that format. The interview replaced the initial one-cycle target with three consecutive real tasks, clarified autonomy, stopping and exception handling, and established evidence-based user assessment and artifact-placement principles. This demonstrates one use of the revised interview; operational closed-loop performance remains unmeasured.
