# Contributing to harness-maker

Thanks for your interest. This guide covers the most common contribution paths: adding a skill or agent template, adding a preset, writing tests in the project's style, and the PR checklist.

## Repo Layout (where things live)

```
harness-maker/
├── src/harness_maker/        # Python source (Pydantic models, pipeline, modules)
│   ├── models.py             # HarnessConfig, Blueprint, FileEntry, ConflictItem, ...
│   ├── profile.py            # M1: stack/scale/lifecycle detection
│   ├── interview.py          # M1: preset + 10+ override dimensions
│   ├── synthesize.py         # M1: preset → Blueprint
│   ├── render.py             # M1: Jinja2 + provenance frontmatter
│   ├── reconcile.py          # M2: brownfield conflict resolution
│   ├── verify.py             # M8: verify-before-completion gate
│   ├── modular_edit.py       # --add / --remove / --promote
│   ├── workflow_fuse.py      # M3: atomic stage fusion
│   ├── conditional_router.py # M6: file-area → reviewer routing
│   ├── autoloop_driver.py    # M7: time/iter-bounded loop
│   ├── worktree.py           # M9: git worktree isolation
│   ├── security_scanner.py   # M10: 7 security gates
│   ├── _metrics_io.py        # shared reader for metrics-YYYY-MM-DD.jsonl (ADR-103, 0.7.1)
│   ├── memory/               # episodic / semantic / profile + _locking.py (ADR-106 re-entrant flock)
│   ├── secscan/              # hallucination + prod_name_guard gate implementations
│   ├── drift_monitor.py      # SPEC↔current trajectory drift (ADR-108 fenced LLM judge)
│   ├── context_lint.py       # M11: render-time context lint
│   ├── provenance.py         # M13: frontmatter (hash, generated_by, ...)
│   ├── readiness.py          # M5: Health (0-100, 6 dimensions)
│   ├── agent_quality.py      # M5: Platinum/Gold/Silver/Bronze rubric
│   ├── crawler/              # M4: 4-source anti-rot crawl
│   ├── relevance.py          # M4: LLM scoring + adaptive threshold
│   ├── recommendation.py     # M16: Confidence-bucketed recommendation registry (Phase 1/4/8 of PLAN-personalization-depth-2026-05)
│   ├── detection_cache.py    # M15: profile cache with manifest-mtime + 24h ceiling invalidation
│   ├── foreign_config.py     # M17: foreign AI config detection + LLM mapping + apply with @hm:harness:* markers
│   ├── personalization_audit.py # M19: /hm:personalization-audit rubric runner per ADR-011
│   ├── rubrics/
│   │   └── personalization.yaml # locked v0 rubric (L1/L2/L3 formulas + tier boundaries)
│   └── i18n.py               # locale-first messaging
├── templates/                # Jinja2 templates (the harness's payload)
│   ├── commands/hm/          # /hm:<stage> + /hm:loop / ai-readiness / refresh
│   ├── skills/<name>/SKILL.md.j2
│   ├── agents/<name>.md.j2
│   ├── stages/<stage>.md.j2  # atomic stage fragments for workflow fusion
│   ├── harness-yaml/<Preset>.yaml.j2
│   ├── settings/<Preset>.json.j2
│   ├── cursor/               # M14: Cursor-only assets (rules/*.mdc, mcp.json)
│   ├── foreign-configs/      # M17: 6 foreign-AI-config templates (cursor_rules / claude_md / agents_md / continue_config / aider_conf / copilot_instructions)
│   └── hooks/                # telemetry hooks
├── commands/make.md          # /harness-maker:make plugin entry
├── .claude-plugin/plugin.json  # Claude Code marketplace manifest
├── .cursor-plugin/plugin.json  # Cursor Marketplace manifest
├── tests/
│   ├── unit/                 # per-module pytest
│   │   └── test_no_network.py # ADR-005 positive obligation (no outbound socket during audit / telemetry)
│   ├── fixtures/             # 4 reference projects (side-python-cli, side-tauri-app, prod-tauri-app, prod-firmware)
│   ├── snapshot/             # golden Blueprint YAMLs + regenerate.py
│   ├── e2e/                  # dogfood + plugin entry
│   └── cursor-compat/        # M14: manual checklist + results grid for Cursor IDE verification
├── docs/                     # this folder
├── TECH_SPEC.md              # source of truth for design decisions
└── .claude-verify.sh         # autoloop-callable phase exit-criteria checker
```

## Adding a New Skill Template

A "skill" is a Jinja2 template under `templates/skills/<name>/SKILL.md.j2` that gets rendered into the user's `.claude/skills/<name>/SKILL.md`.

Steps:

1. **Pick a name.** Lowercase, hyphenated, descriptive (e.g. `worktree-isolator`, not `wkt`).
2. **Create the template.**

   ```
   templates/skills/<name>/SKILL.md.j2
   ```

   Start the file with frontmatter — the **provenance invariant** (verified by `phase_<N>_invariants` in `.claude-verify.sh`) requires every generated `.md`/`.json` to begin with `---`.

   ```jinja
   ---
   generated_by: harness-maker
   harness_maker_version: "{{ version }}"
   source_template: templates/skills/<name>/SKILL.md.j2
   content_hash: "{{ content_hash }}"
   generated_at: "{{ now }}"
   provenance: synthesized
   ---
   # <Skill Title>

   <body — instructions to the LLM, examples, triggers>
   ```

3. **Wire it into the synthesizer.** Open `src/harness_maker/synthesize.py` and add a `FileEntry` for the new skill in the appropriate preset path. Reference the template path; pass the context the template needs.
4. **Add to `final_acceptance` in `.claude-verify.sh`.** The "Skills (11) presence" loop enumerates required templates. Increment the count and add your skill name.
5. **Write a test.** Add a unit test under `tests/unit/` that renders the template against a `Blueprint` fixture and asserts the output starts with `---` and contains expected markers.
6. **Regenerate snapshots if the Blueprint shape changed.**

   ```bash
   uv run python tests/snapshot/regenerate.py
   ```

## Adding a New Agent Template

Same pattern as skills, with two differences:

1. Path: `templates/agents/<name>.md.j2` (single file, no folder).
2. **Privilege separation matters (M12).** Both reviewer and executor agents declare structured `permissions: {allow: [...], deny: [...]}` in their YAML frontmatter (so Cursor 2.5+ enforces per-agent — parent → subagent inheritance is broken).
   - Reviewer-style agents: `deny` MUST include `Write(*)`, `Edit(*)`, `Bash(rm:*)`, `Bash(curl:*)`, `Bash(npm:*)`, `Bash(eval *)`, plus the interpreter set `Bash(python:*)`, `Bash(node:*)`, `Bash(sh:*)`, `Bash(bash:*)` (the latter four added 0.6.2 to close subprocess-bypass via `python -c "..."`).
   - Executor-style agents: `allow` includes `Write(.worktrees/**)`, `Edit(.worktrees/**)`, plus scoped Bash test commands. `deny` MUST pair `Write` and `Edit` for every system path — `Write(/etc/**)` without `Edit(/etc/**)` is an escalation gap (0.6.2 REVIEW M1).
   - The `phase_10_reviewer_perms` and `phase_10_executor_perms` checks in `.claude-verify.sh` will fail if you mix these up. CI snapshot test `test_render_agents_have_structured_permissions_frontmatter` guards the structural shape. See `templates/agents/code-reviewer.md.j2` (reviewer pattern) and `templates/agents/executor.md.j2` (executor pattern) as references.
3. Update the "Agents (9) presence" loop in `.claude-verify.sh`'s `final_acceptance`.

## Adding Cursor target support to a new template

If your new skill, agent, or command needs a Cursor-specific variant:

1. **Check if single-source is enough.** For most templates, Cursor 2.4+ reads `.claude/agents/` and `.claude/skills/` natively — no extra file needed.
2. **Only add a Cursor-specific file if the content must differ** (e.g., a rules file at `.cursor/rules/`).
3. **Use `_render_cursor_mdc()` dispatch in `render.py`** when the output is a `.mdc` file. This limits frontmatter to `description`, `globs`, and `alwaysApply` — Cursor rejects unknown keys. Do **not** include `content_hash` in the frontmatter; use a sidecar `.hm-meta.yaml` if hash-tracking is needed.
4. **Use `_render_pure_text()` dispatch** for `.json` files like `.cursor/mcp.json` — no frontmatter allowed.
5. **Gate the render** with `if cursor in config.targets` in `synthesize.py`.
6. **Add a manual checklist row** in `tests/cursor-compat/MANUAL_CHECKLIST.md` for the new asset.

## Adding a New Preset

Presets live in two paired templates:

```
templates/harness-yaml/<Preset>.yaml.j2   # the harness.yaml schema instance
templates/settings/<Preset>.json.j2        # the settings.json (permissions, hooks)
```

Steps:

1. **Add the enum.** Open `src/harness_maker/models.py`, extend the `Preset` enum.

   ```python
   class Preset(str, Enum):
       SIDE = "Side"
       PRODUCTION = "Production"
       MY_NEW_PRESET = "MyNewPreset"
   ```

2. **Add the synthesizer mapping.** In `src/harness_maker/synthesize.py`, extend the preset→reviewer/workflow/model mapping. Use `TECH_SPEC.md` Section 3 "Preset default comparison" as the schema reference for which dimensions a preset must define.
3. **Render templates.** Create `templates/harness-yaml/MyNewPreset.yaml.j2` and `templates/settings/MyNewPreset.json.j2`. Copy from `Side.yaml.j2` (lean) or `Production.yaml.j2` (full) as starting point.
4. **Add a fixture.** Create `tests/fixtures/<scenario>-mynewpreset/` with a minimal project shape (pyproject.toml or package.json or Cargo.toml). Add the corresponding `tests/snapshot/<scenario>-mynewpreset.expected.yaml`.
5. **Update `final_acceptance`.** Add your preset to the `for p in Side Production` loop in `.claude-verify.sh`.
6. **Update README's preset table** if the new preset is user-facing.

## Test Patterns

The codebase uses pytest with three layers:

| Layer | Path | What it tests |
|---|---|---|
| Unit | `tests/unit/` | Single module: `test_models.py`, `test_render.py`, `test_synthesize.py`, ... |
| Snapshot | `tests/snapshot/` + `tests/unit/test_synthesize_snapshot.py` | Blueprint YAML output for the 4 fixture projects matches golden file |
| E2E | `tests/e2e/` | `test_dogfood_sandbox.py` (full pipeline against sandbox), `test_plugin_entry.py` (plugin manifest) |

Conventions:

- **Use `tmp_path` for filesystem tests.** Never write under repo root.
- **Use `monkeypatch` for time/locale/env, not module-level mutation.**
- **Property-based tests are encouraged** for parsing or hash logic — the codebase uses `hypothesis`.
- **One assertion per behavior.** Don't combine unrelated checks via `and` (ruff `PT018` will flag it).
- **Line length: 100.** ruff `E501` will flag overruns.
- **Frontmatter assertion pattern:**

  ```python
  for md in md_files:
      head = md.read_text(encoding="utf-8").splitlines()[:1]
      assert head, f"{md} is empty"
      assert head[0] == "---", f"{md} missing frontmatter"
  ```

To regenerate snapshots after a Blueprint shape change:

```bash
uv run python tests/snapshot/regenerate.py
```

Run the verify script for the phase you touched:

```bash
bash .claude-verify.sh phase_3              # full Phase 3 exit criteria
bash .claude-verify.sh phase_3_render       # just the render task
bash .claude-verify.sh phase_3_invariants   # frontmatter invariants only
```

## Local Setup

After cloning, install the pre-commit hook once. It auto-runs `ruff format` +
`ruff check --fix` on every `git commit`, catching the same failure CI's
quality-gate job catches — but locally, before the push.

```bash
uv sync
uv run pre-commit install
```

To run the hook manually across the whole repo: `uv run pre-commit run --all-files`.

## Pull Request Checklist

Before opening a PR:

- [ ] `uv run pre-commit install` once after cloning (one-time)
- [ ] `uv run ruff format src/ tests/` — formatted
- [ ] `uv run ruff check src/ tests/` — 0 errors
- [ ] `uv run mypy --strict src/` — 0 errors
- [ ] `uv run pytest tests/ -q` — all pass
- [ ] `bash .claude-verify.sh phase_<N>` for the phase you touched — passes
- [ ] `bash .claude-verify.sh final_acceptance` — still passes
- [ ] If you added/changed a Blueprint field: snapshots regenerated (`uv run python tests/snapshot/regenerate.py`) and reviewed in the diff
- [ ] If you added a skill/agent/preset: enumerated in `.claude-verify.sh final_acceptance`
- [ ] If you added a template: starts with `---` frontmatter (provenance invariant)
- [ ] `TECH_SPEC.md` updated if the change touches a Section 3 mechanism (M1-M14) or Section 5 acceptance criteria
- [ ] If bumping the version: all **4 files** updated in the same commit: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`
- [ ] Commit message follows `<type>(phase<N>): <description>` (e.g. `feat(phase4): add anti-rot adaptive threshold`)

## Reporting Issues

Include:

- Output of `bash .claude-verify.sh <relevant_phase>`
- Your preset, locale, and (if relevant) anonymized `harness.yaml`
- Whether the issue reproduces against a clean fixture (`tests/fixtures/side-python-cli/`)

## Code of Conduct

Be kind. Critique ideas, not people. Write commit messages and PR descriptions you'd want to read at 2am while debugging.
