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
│   ├── security_scanner.py   # M10: 5 security gates
│   ├── context_lint.py       # M11: render-time context lint
│   ├── provenance.py         # M13: frontmatter (hash, generated_by, ...)
│   ├── readiness.py          # M5: Health (0-100, 6 dimensions)
│   ├── agent_quality.py      # M5: Platinum/Gold/Silver/Bronze rubric
│   ├── statusline.py         # M5: 효율/Health/fresh status line
│   ├── crawler/              # M4: 4-source anti-rot crawl
│   ├── relevance.py          # M4: LLM scoring + adaptive threshold
│   └── i18n.py               # locale-first messaging
├── templates/                # Jinja2 templates (the harness's payload)
│   ├── commands/hm/          # /hm:<stage> + /hm:loop / monitor / refresh
│   ├── skills/<name>/SKILL.md.j2
│   ├── agents/<name>.md.j2
│   ├── stages/<stage>.md.j2  # atomic stage fragments for workflow fusion
│   ├── harness-yaml/<Preset>.yaml.j2
│   ├── settings/<Preset>.json.j2
│   └── hooks/                # statusline + telemetry hooks
├── commands/make.md          # /harness-maker:make plugin entry
├── tests/
│   ├── unit/                 # per-module pytest
│   ├── fixtures/             # 4 reference projects (side-python-cli, side-tauri-app, prod-tauri-app, prod-firmware)
│   ├── snapshot/             # golden Blueprint YAMLs + regenerate.py
│   └── e2e/                  # dogfood + plugin entry
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
4. **Add to `final_acceptance` in `.claude-verify.sh`.** The "Skills (10) 존재" loop enumerates required templates. Increment the count and add your skill name.
5. **Write a test.** Add a unit test under `tests/unit/` that renders the template against a `Blueprint` fixture and asserts the output starts with `---` and contains expected markers.
6. **Regenerate snapshots if the Blueprint shape changed.**

   ```bash
   uv run python tests/snapshot/regenerate.py
   ```

## Adding a New Agent Template

Same pattern as skills, with two differences:

1. Path: `templates/agents/<name>.md.j2` (single file, no folder).
2. **Privilege separation matters (M12).** Reviewer-style agents must declare `permissions.deny: [Write, Edit, Bash exec]` in their frontmatter; executor-style agents get `permissions.allow: [Write(.worktrees/**)]`. The `phase_10_reviewer_perms` and `phase_10_executor_perms` checks in `.claude-verify.sh` will fail if you mix these up. See `templates/agents/code-reviewer.md.j2` (reviewer pattern) and `templates/agents/executor.md.j2` (executor pattern) as references.
3. Update the "Agents (9) 존재" loop in `.claude-verify.sh`'s `final_acceptance`.

## Adding a New Preset

Presets live in two paired templates:

```
templates/harness-yaml/<Preset>.yaml.j2   # the harness.yaml schema instance
templates/settings/<Preset>.json.j2        # the settings.json (statusLine, permissions, hooks)
```

Steps:

1. **Add the enum.** Open `src/harness_maker/models.py`, extend the `Preset` enum.

   ```python
   class Preset(str, Enum):
       SIDE = "Side"
       PRODUCTION = "Production"
       MY_NEW_PRESET = "MyNewPreset"
   ```

2. **Add the synthesizer mapping.** In `src/harness_maker/synthesize.py`, extend the preset→reviewer/workflow/model mapping. Use `TECH_SPEC.md` Section 3 "Preset 디폴트 비교" as the schema reference for which dimensions a preset must define.
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

## Pull Request Checklist

Before opening a PR:

- [ ] `uv run ruff format src/ tests/` — formatted
- [ ] `uv run ruff check src/ tests/` — 0 errors
- [ ] `uv run mypy --strict src/` — 0 errors
- [ ] `uv run pytest tests/ -q` — all pass
- [ ] `bash .claude-verify.sh phase_<N>` for the phase you touched — passes
- [ ] `bash .claude-verify.sh final_acceptance` — still passes
- [ ] If you added/changed a Blueprint field: snapshots regenerated (`uv run python tests/snapshot/regenerate.py`) and reviewed in the diff
- [ ] If you added a skill/agent/preset: enumerated in `.claude-verify.sh final_acceptance`
- [ ] If you added a template: starts with `---` frontmatter (provenance invariant)
- [ ] `TECH_SPEC.md` updated if the change touches a Section 3 mechanism (M1-M13) or Section 5 acceptance criteria
- [ ] Commit message follows `<type>(phase<N>): <description>` (e.g. `feat(phase4): add anti-rot adaptive threshold`)

## Reporting Issues

Include:

- Output of `bash .claude-verify.sh <relevant_phase>`
- Your preset, locale, and (if relevant) anonymized `harness.yaml`
- Whether the issue reproduces against a clean fixture (`tests/fixtures/side-python-cli/`)

## Code of Conduct

Be kind. Critique ideas, not people. Write commit messages and PR descriptions you'd want to read at 2am while debugging.
