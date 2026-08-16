# Codex runtime probe — sub-agent dispatch, user input, skill invocation

Every Codex-internal claim in `PLAN-codex-lens-dispatch` comes from a probe, not from
documentation. This file records the commands and their captured output so a future reader
re-runs them instead of re-deriving them.

That standard exists because this repo has twice built an ADR on a mis-spelled flag that read
as authoritative once copied: `agy --print --sandbox …` (which fed `--sandbox` to the model as
the prompt) and `--output-schema` (whose antigravity spelling is `--json-schema`). Both were
believed for months. See `tests/manual/ANTIGRAVITY_SANDBOX_PROBE.md` for the same pattern.

**Environment at capture time:** `codex-cli 0.147.0`, run from `~/strange_chess` (a rendered
harness with `preset: Side`, `targets: [claude-code, codex]`), 2026-08-16.

---

## 1. Does Codex have a sub-agent tool, and what are its parameters?

```bash
codex exec --sandbox read-only "Call the list_agents tool and report verbatim the JSON it returns. Then state the exact parameter names of the spawn_agent tool schema. Do not do anything else."
```

Output (verbatim):

```
`list_agents` 도구가 이 세션에 없어 반환된 JSON이 없습니다.

`spawn_agent` 매개변수명: `agent_type`, `fork_context`, `items`, `message`, `model`,
`reasoning_effort`, `service_tier`
```

**Findings.** `spawn_agent` exists. Its dispatch parameters are `agent_type` and `message` —
the direct analogues of Claude's `subagent_type` and `prompt`. `list_agents` was **not** exposed
in this `exec` session.

**Caveat that survives into ADR-002.** The shipped binary also contains a `multi_agents_v2`
handler set (`core/src/tools/handlers/multi_agents_v2/{spawn,wait,list_agents,send_message,
followup_task,interrupt_agent}.rs`) whose embedded prose describes `task_name` and `fork_turns`
instead. Two schemas coexist and only the `exec` one is verified here. That is why the rendered
dispatch puts a runtime-neutral **intent sentence first** and the literal second: a drifted
parameter name then degrades to "the model reads the intent and adapts" rather than to a silent
no-op.

Binary strings confirming the second handler set and the event names the e2e asserts on:

```bash
B=$(dirname $(readlink -f $(which codex)))/../node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
strings -n 4 "$B" | grep -n "multi_agents_v2"
strings -n 4 "$B" | grep -oE "\bcollab_agent_spawn_(begin|end)\b|\bsub_agent_activity\b" | sort -u
```

## 2. Are agent roles resolved from `.codex/config.toml`?

`codex features list` reports `multi_agent  stable  true`. The binary carries
`core/src/config/agent_roles.rs` with the errors `duplicate agent role name`,
`agents.<name>.config_file must point to a file` and `agents.<name>.nickname_candidates` — i.e.
the `[agents.*]` table harness-maker already renders **is** Codex's agent-role registry. No
name-mapping table is needed: `agent_type` takes the same name Claude's `subagent_type` takes,
because both come from the same `agents` dict in `synthesize`.

## 3. What does Codex use instead of `AskUserQuestion`?

```bash
codex exec --sandbox read-only "State the exact parameter names of the request_user_input tool schema, and whether it is available in this session. One short answer, in English. Do nothing else."
```

Output (verbatim):

```
`request_user_input` is available. Parameters: `questions`; nested fields `header`, `id`,
`options`, `question`, `description`, `label`.
```

**Finding.** Near-identical in shape to `AskUserQuestion`, minus `multiSelect`. Available in
`exec`, so it is not interactive-only.

## 4. Can Codex invoke a skill programmatically? (No.)

```bash
codex exec --sandbox read-only "List the exact names of any tools available to you that invoke or run a SKILL (not an agent). If none exist, say 'none'. Then state how a skill in .agents/skills/ gets invoked in your session. Two short lines, English."
```

Output (verbatim):

```
SKILL-running tools: none.
A skill in `.agents/skills/` is invoked by mentioning its skill name (e.g. `@hm-execute`).
```

**Findings, both load-bearing.**

- **Autopilot auto-advance is genuinely impossible on Codex**, and harness-maker suppressing the
  auto-advance block there (`stage_end_summary.md.j2`, gated on `is_codex`) is correct rather
  than conservative. Arming still works in every runtime — only the advance needs a tool Codex
  does not have. Shipping the block anyway would be the same defect as shipping `Task(`.
- **The `Next:` banner must name the mention form.** `/hm:execute` is not callable on Codex, so
  `template_globals.stage_invocation` rewrites `/hm:<stage>` to `@hm-<stage>` on that arm.

## 5. Is the plugin's own `commands/make.md` reachable from Codex? (No evidence.)

```bash
codex plugin list
```

Shows only the `openai-curated` marketplace; harness-maker is not a Codex-installable plugin
here. `.codex-plugin/plugin.json` is bare metadata — **no `commands` key**, no asset mapping —
and `README.md:278-294` routes Codex first-run through Bash `harness-maker make` precisely
because `.agents/skills/` are generated *by* that step.

**This is why ADR-007 was withdrawn.** It would have bought 46 rewrites in `commands/make.md`,
plus an accepted degradation of the Claude interview, for a surface with no evidence of ever
being reached. If Codex later gains plugin `commands` support, re-run this one command and the
decision becomes re-decidable rather than re-derivable.
