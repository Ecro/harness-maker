"""SPEC-maker-front-door-improvements Phase 4: Maker is the only entrance — rendered surfaces
(AC-001, 002, 003, 004, 005, 007, 010, 014, 016, 017).

Every literal asserted here is the PLAN ADR-008 string contract (ADR-007 amendment for the
injected command), not a paraphrase of the current templates. Renders go through the real
`make` CLI so the reconcile/orphan-sweep path is the one users hit.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from harness_maker.cli import app
from harness_maker.spec_machine import load_golden_table
from harness_maker.world_model import HANDLE_MAX, NAME_MAX

_REPO = Path(__file__).resolve().parents[2]
_SPEC_YAML = _REPO / "specs/SPEC-maker-front-door-improvements.machine.yaml"

_STAGES = ("research", "spec", "execute", "review", "verify", "wrapup")
_KNOWLEDGE_SKILLS = ("intent-layer", "project-knowledge")
_MAKER_CAP = 4500
_POINTER_CAP = 400
_PK_POINTER_CAP = 300
_TRIGGER_PHRASES = ("invoke when", "use when", "use this when")

_CONSENT = "Its consent rule applies unchanged."
_BRIEFING_FIRST = (
    "Answer read-only goal and status questions from the briefing; "
    "read a procedure only to change something."
)
_DECISION_RULE = (
    "write it into that task's most downstream artifact (PLAN, else SPEC, else RESEARCH) "
    "before replying"
)
_RESUME_LATEST = "name its latest_artifact and time before entering"
_MAKER_ASIDE = ("at most 6 lines", "`## Queued asks`", "never start", "↩")
# ADR-008 (A.5 round 1): the line bound and the opener are pinned per locale, not a bare digit.
_POINTER_ASIDE = ("`## Queued asks`", "↩")
_POINTER_ASIDE_BY_LOCALE: dict[str, tuple[str, ...]] = {"en": ("6 lines",), "ko": ("6줄",)}
_POINTER_OPENER_BY_LOCALE: dict[str, str] = {
    "en": "asides start `{name} —`",
    "ko": "곁답은 `{name} —`로 시작",
}
_MAKER_OPENER = "Mid-stage asides start `{name} —`"
_EXCLUSION_BY_LOCALE: dict[str, str] = {"en": "not build/fix", "ko": "만들기·고치기 제외"}
_DESCRIPTION_ROUTE = "or the World model rule routes a goal, metric, fact or status request here"
_NARROW = "hm autopilot narrow --until"
_UNCLEAR = "unclear → research"
# codex a1231bf6: an ask that ends at research must also ENTER research, never spec.
_RESEARCH_ENTRY = "when the end is research"
_END_STAGE_CUES = {
    "research": ("research", "리서치", "조사"),
    "spec": ("spec", "스펙"),
    "full": ("build", "만들어", "고쳐"),
}
# REVIEW 24451777 (DRI-approved oracle change, round 2): the uv grant is scoped to this
# harness's own `hm` — `{hm}` is filled from the rendered "`hm` below means `…`" line, the same
# shape as the settings templates' `Bash(uv run --with <src> hm *)`. A bare `Bash(uv run:*)`
# pre-approved any `uv run` and must never come back.
# REVIEW confirm-1 P1 (DRI-approved oracle change, same authorisation as 24451777): `hm *` still
# pre-approved every hm verb; the grant is exactly the two verbs Maker runs plus the fallback.
_ALLOWED_TOOLS = (
    # `world_model` has one subcommand, the read-only `digest`; naming the module keeps the
    # grant out of the single-digest classifier (test_ac_007_router_single_digest).
    "Bash({hm} world_model:*)",
    "Bash({hm} autopilot narrow:*)",
    # tail/grep/printf: the ungrouped `| tail -n 1 | grep '^{.*}$' || printf` fail-soft chain
    # (post-review confirm-2 P2 — a `{ …; }` group matched no prefix rule).
    "Bash(tail:*)",
    "Bash(grep:*)",
    "Bash(printf:*)",
)
_BARE_UV_GRANT = "Bash(uv run:*)"
_HM_WILDCARD_SUFFIX = "hm *)"
_HM_MEANS = re.compile(r"`hm` below means `([^`]+)`")

_MAX_NAME = "N" * NAME_MAX
_MAX_HANDLE = "h" * HANDLE_MAX

# name, handle, locale, CLI args. "ko" deliberately uses a non-default name so a template that
# hard-codes "Maker" / "maker" fails there.
_CONFIGS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "en": ("Maker", "maker", "en", ("--targets", "claude-code,cursor,codex")),
    "ko": ("비비", "bibi", "ko", ("--targets", "claude-code,cursor,codex")),
    "en_max": (_MAX_NAME, _MAX_HANDLE, "en", ("--targets", "claude-code,cursor,codex")),
    "ko_max": (_MAX_NAME, _MAX_HANDLE, "ko", ("--targets", "claude-code,cursor,codex")),
    "cursor": ("Bibi", "bibi", "en", ("--targets", "cursor")),
}


@contextmanager
def _chdir(path: Path) -> Iterator[None]:
    before = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(before)


def _cli(repo: Path, *args: str) -> Any:
    with _chdir(repo):
        return CliRunner().invoke(app, ["make", str(repo), "--autoloop", *args])


def _bootstrap(root: Path, *args: str) -> Path:
    repo = root / "proj"
    repo.mkdir(parents=True)
    res = _cli(repo, *args)
    assert res.exit_code == 0, res.output
    return repo


def _args(config: str) -> tuple[str, ...]:
    name, handle, locale, extra = _CONFIGS[config]
    return (
        "--locale",
        locale,
        *extra,
        "--world-model-name",
        name,
        "--world-model-handle",
        handle,
    )


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    """Render each named configuration once per module, on first use."""
    cache: dict[str, Path] = {}

    def get(config: str) -> Path:
        if config not in cache:
            cache[config] = _bootstrap(tmp_path_factory.mktemp(config), *_args(config))
        return cache[config]

    return get


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, Any]:
    assert text.startswith("---\n"), "no leading frontmatter"
    data = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(data, dict)
    return data


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    ends = [i for i in (text.find("\n## ", start + 1), text.find("\n<!--", start + 1)) if i != -1]
    return (text[start : min(ends)] if ends else text[start:]).rstrip()


def _maker_rel(runtime: str, handle: str) -> str:
    return (
        f".agents/skills/{handle}/SKILL.md"
        if runtime == "codex"
        else (f".claude/skills/{handle}/SKILL.md")
    )


def _invocation(runtime: str, handle: str) -> str:
    return f"${handle}" if runtime == "codex" else f"/{handle}"


# ---------------------------------------------------------------------------
# AC-001 — intent-layer / project-knowledge are not model-invocable (Claude Code, Cursor)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill", _KNOWLEDGE_SKILLS)
@pytest.mark.parametrize("config", ["en", "cursor"], ids=["claude-code", "cursor"])
def test_ac001_skills_not_model_invocable(
    config: str, skill: str, repo: Callable[[str], Path]
) -> None:
    fm = _frontmatter(_read(repo(config), f".claude/skills/{skill}/SKILL.md"))
    assert fm.get("name") == skill
    assert fm.get("disable-model-invocation") is True, fm


# ---------------------------------------------------------------------------
# AC-002 — Codex implicit invocation off via agents/openai.yaml; removed with codex
# ---------------------------------------------------------------------------

_AC002 = load_golden_table(_SPEC_YAML, "AC-002")
_OPENAI_YAML_TEXT = "policy:\n  allow_implicit_invocation: false\n"


def _ac002_id(row: Any) -> str:
    t = row.input["targets"]
    return f"{'+'.join(t) if isinstance(t, list) else 'sweep'}-{row.input['skill']}"


@pytest.mark.parametrize("row", _AC002, ids=[_ac002_id(r) for r in _AC002])
def test_ac002_codex_implicit_invocation_off(row: Any, tmp_path: Path) -> None:
    skill = row.input["skill"]
    rel = f".agents/skills/{skill}/agents/openai.yaml"
    targets = row.input["targets"]
    sweep = not isinstance(targets, list)
    proj = _bootstrap(tmp_path, "--targets", "claude-code,codex" if sweep else ",".join(targets))

    if sweep:
        # Precondition: the file exists under codex, so its absence afterwards is the sweep.
        assert (proj / rel).is_file(), f"{rel} not rendered with codex in targets"
        res = _cli(proj, "--update", "--targets", "claude-code")
        assert res.exit_code == 0, res.output
        assert row.expected["swept"] is True
        assert not (proj / ".agents/skills" / skill / "SKILL.md").exists()  # sweep really ran

    exists = (proj / rel).is_file()
    assert exists is row.expected["exists"], rel
    if not exists:
        return
    text = _read(proj, rel)
    docs = list(yaml.safe_load_all(text))
    assert len(docs) == 1, "openai.yaml must be one YAML document (no provenance preamble)"
    assert docs[0] == {"policy": {"allow_implicit_invocation": False}}
    want = row.expected["policy.allow_implicit_invocation"]
    assert docs[0]["policy"]["allow_implicit_invocation"] is want
    assert text == _OPENAI_YAML_TEXT
    # ADR-008: the Claude flag is not copied into the Codex SKILL.md.
    codex_fm = _frontmatter(_read(proj, f".agents/skills/{skill}/SKILL.md"))
    assert "disable-model-invocation" not in codex_fm


# ---------------------------------------------------------------------------
# AC-003 — /hm: stage descriptions are entrance-gated, never hard-flagged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage", _STAGES)
@pytest.mark.parametrize("runtime", ["claude-code", "codex"])
@pytest.mark.parametrize("config", ["en", "ko"])
def test_ac003_stage_descriptions_gated(
    config: str, runtime: str, stage: str, repo: Callable[[str], Path]
) -> None:
    name = _CONFIGS[config][0]
    root = repo(config)
    if runtime == "codex":
        text = _read(root, f".agents/skills/hm-{stage}/SKILL.md")
        loop = "$hm-loop"
    else:
        text = _read(root, f".claude/commands/hm/{stage}.md")
        loop = "/hm:loop"
    fm = _frontmatter(text)
    desc = str(fm["description"])
    gate = f"Only when typed, or via {name}, autopilot or {loop}."
    for token in ("typed", name, "autopilot", loop):
        assert token in desc, (token, desc)
    assert gate in desc, desc
    summary = desc.replace(gate, "").strip()
    assert len(summary) >= 20, f"summary dropped: {desc!r}"
    hits = [p for p in _TRIGGER_PHRASES if p in desc.lower()]
    assert hits == [], desc
    assert "disable-model-invocation" not in fm
    assert "disable-model-invocation" not in text


# ---------------------------------------------------------------------------
# AC-004 — project-knowledge pointer and /hm:help rows route to Maker
# ---------------------------------------------------------------------------

_PK_POINTERS = [
    ("en", "CLAUDE.md", "claude-code", ".claude/skills"),
    ("ko", "CLAUDE.md", "claude-code", ".claude/skills"),
    ("en", ".cursor/rules/harness.mdc", "cursor", ".claude/skills"),
    ("en", "AGENTS.md", "codex", ".agents/skills"),
]


@pytest.mark.parametrize(
    ("config", "rel", "runtime", "skills_dir"),
    _PK_POINTERS,
    ids=["claude-en", "claude-ko", "cursor", "codex"],
)
def test_ac004_pointers_route_to_maker(
    config: str, rel: str, runtime: str, skills_dir: str, repo: Callable[[str], Path]
) -> None:
    _, handle, _, _ = _CONFIGS[config]
    section = _section(_read(repo(config), rel), "## Project knowledge")
    assert len(section) <= _PK_POINTER_CAP, (len(section), section)
    for keep in ("project-knowledge", "auto-memory"):
        assert keep in section, keep
    assert _invocation(runtime, handle) in section, section
    assert f"{skills_dir}/project-knowledge/SKILL.md" in section, section
    assert "follow the `project-knowledge` skill" not in section
    assert "skill 을 따른다" not in section


@pytest.mark.parametrize("skill", _KNOWLEDGE_SKILLS)
@pytest.mark.parametrize("runtime", ["claude-code", "codex"])
@pytest.mark.parametrize("config", ["en", "ko"])
def test_ac004_help_rows_typed_only(
    config: str, runtime: str, skill: str, repo: Callable[[str], Path]
) -> None:
    _, handle, _, _ = _CONFIGS[config]
    rel = ".agents/skills/hm-help/SKILL.md" if runtime == "codex" else ".claude/commands/hm/help.md"
    rows = [ln for ln in _read(repo(config), rel).splitlines() if ln.startswith(f"| {skill} |")]
    assert len(rows) == 1, rows
    assert "typed only" in rows[0], rows[0]
    assert _invocation(runtime, handle) in rows[0], rows[0]


# ---------------------------------------------------------------------------
# AC-005 — Maker reads the procedures on demand, every target, ≤ 4,500 chars
# ---------------------------------------------------------------------------

_MAKER_ARMS = [
    ("en", "claude-code"),
    ("ko", "claude-code"),
    ("cursor", "cursor"),
    ("en", "codex"),
    ("ko", "codex"),
]
_MAKER_IDS = ["claude-code-en", "claude-code-ko", "cursor", "codex-en", "codex-ko"]


def _maker(repo: Callable[[str], Path], config: str, runtime: str) -> str:
    return _read(repo(config), _maker_rel(runtime, _CONFIGS[config][1]))


@pytest.mark.parametrize(("config", "runtime"), _MAKER_ARMS, ids=_MAKER_IDS)
def test_ac005_maker_reads_procedures(
    config: str, runtime: str, repo: Callable[[str], Path]
) -> None:
    text = _maker(repo, config, runtime)
    skills_dir = ".agents/skills" if runtime == "codex" else ".claude/skills"
    paths = [f"{skills_dir}/{n}/SKILL.md" for n in _KNOWLEDGE_SKILLS]
    read_lines = [
        i for i, ln in enumerate(text.splitlines()) if "Read" in ln and all(p in ln for p in paths)
    ]
    assert read_lines, f"no Read line naming {paths}"
    read_at = len("\n".join(text.splitlines()[: read_lines[0]]))
    edits = [text.find(v) for v in ("hm intent ", "hm memory_md") if text.find(v) != -1]
    assert all(e > read_at for e in edits), "an edit verb precedes the procedure Read"
    assert _CONSENT in text
    assert _BRIEFING_FIRST in text
    assert _DESCRIPTION_ROUTE in str(_frontmatter(text)["description"])
    assert len(text) <= _MAKER_CAP, len(text)


# ---------------------------------------------------------------------------
# AC-007 — Maker maps the operator's ask to an end stage (DRI golden table)
# ---------------------------------------------------------------------------

_AC007 = load_golden_table(_SPEC_YAML, "AC-007")


def _tables(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    cur: list[str] = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("|"):
            cur.append(ln)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    return blocks


def _end_stage_table(text: str) -> list[str]:
    """The table that carries cue rows for all three end stages (ADR-008)."""
    for block in _tables(text):
        rows = [r for r in block if not re.fullmatch(r"\|[\s:|-]*\|?", r.strip())]
        if all(any(any(c in r for c in cues) for r in rows) for cues in _END_STAGE_CUES.values()):
            return rows
    raise AssertionError("no end-stage table with research/spec/full cue rows")


@pytest.mark.parametrize("runtime", ["claude-code", "codex"])
@pytest.mark.parametrize("row", _AC007, ids=[r.input["case"] for r in _AC007])
def test_ac007_ask_to_end_stage(row: Any, runtime: str, repo: Callable[[str], Path]) -> None:
    text = _maker(repo, "en", runtime)
    assert _NARROW in text
    table = _end_stage_table(text)
    case = str(row.input["case"])
    expected = str(row.expected["end_stage"])
    all_cues = [c for cues in _END_STAGE_CUES.values() for c in cues]
    case_cues = [c for c in all_cues if c in case]
    if expected == "research":
        stage = "$hm-research" if runtime == "codex" else "/hm:research"
        assert f"Enter `{stage}` {_RESEARCH_ENTRY}" in " ".join(text.split()), stage
    if not case_cues:
        assert _UNCLEAR in text
        assert expected == "research"
        return
    matched = [r for r in table if any(c in r for c in case_cues)]
    assert len(matched) == 1, (case_cues, matched)
    # REVIEW f084ce96 / codex ed3f3031: the cue match alone never read the mapped stage — the
    # Ends-at cell of the matched row must name the golden end_stage.
    cells = [c.strip() for c in matched[0].strip().strip("|").split("|")]
    assert len(cells) == 2, cells
    ends_at = cells[1]
    if expected == "full":
        assert "full pipeline" in ends_at, (expected, ends_at)
    else:
        assert ends_at == expected, (expected, ends_at)
    own = _END_STAGE_CUES[expected]
    assert all(c in matched[0] for c in own), (expected, matched[0])
    for other, cues in _END_STAGE_CUES.items():
        if other != expected:
            assert not any(c in matched[0] for c in cues if c not in own), (other, matched[0])


# ---------------------------------------------------------------------------
# AC-010 — the injected digest command never aborts Maker
# ---------------------------------------------------------------------------

_AC010 = load_golden_table(_SPEC_YAML, "AC-010")
_FAKE_UV = {
    "digest succeeds": "printf '%s\\n' '{\"tasks\":[],\"more\":0}'\nexit 0\n",
    "cache path missing": "exit 2\n",
    "partial stdout then non-zero": "printf '{\"tasks\":['\nexit 1\n",
}


def _injected_command(text: str, runtime: str) -> str:
    if runtime == "codex":
        blocks = re.findall(r"```bash\n(.*?)\n```", text, flags=re.S)
        cmds = [b.strip() for b in blocks if "world_model digest" in b]
    else:
        cmds = re.findall(r"^!`(.+)`\s*$", text, flags=re.M)
    assert len(cmds) == 1, cmds
    return str(cmds[0])


def _json_objects(out: str) -> list[Any] | None:
    dec = json.JSONDecoder()
    objs: list[Any] = []
    i = 0
    while i < len(out):
        if out[i].isspace():
            i += 1
            continue
        try:
            obj, i = dec.raw_decode(out, i)
        except ValueError:
            return None
        objs.append(obj)
    return objs


def _tool_path(tmp: Path, *, with_uv: str | None) -> str:
    tools = tmp / "tools"
    tools.mkdir()
    for tool in ("tail", "head", "cat", "grep"):
        found = shutil.which(tool)
        assert found is not None, tool
        (tools / tool).symlink_to(found)
    if with_uv is None:
        return str(tools)
    fake = tmp / "fakebin"
    fake.mkdir()
    uv = fake / "uv"
    uv.write_text("#!/bin/sh\n" + with_uv, encoding="utf-8")
    uv.chmod(0o755)
    return f"{fake}{os.pathsep}{tools}"


@pytest.mark.parametrize("runtime", ["claude-code", "codex"])
@pytest.mark.parametrize("row", _AC010, ids=[r.input["case"] for r in _AC010])
def test_ac010_injected_command_fail_soft(
    row: Any, runtime: str, repo: Callable[[str], Path], tmp_path: Path
) -> None:
    text = _maker(repo, "en", runtime)
    cmd = _injected_command(text, runtime)
    assert "world_model digest" in cmd
    assert '"unavailable"' in cmd, f"no fail-soft fallback in {cmd!r}"
    if runtime == "claude-code":
        tools = _frontmatter(text).get("allowed-tools")
        assert tools is not None, "Maker frontmatter has no allowed-tools"
        listed = " ".join(tools) if isinstance(tools, list) else str(tools)
        hm = _HM_MEANS.search(text)
        assert hm is not None, "Maker never says what `hm` expands to"
        assert hm.group(1).startswith("uv run --with "), hm.group(1)
        assert hm.group(1).endswith(" hm"), hm.group(1)
        for pattern in _ALLOWED_TOOLS:
            assert pattern.format(hm=hm.group(1)) in listed, (pattern, tools)
        entries = (
            [str(t).strip() for t in tools]
            if isinstance(tools, list)
            else [e.strip() for e in re.split(r",\s*(?=Bash\()", str(tools))]
        )
        assert _BARE_UV_GRANT not in entries, entries
        assert entries == [p.format(hm=hm.group(1)) for p in _ALLOWED_TOOLS], entries
        assert not any(e.endswith(_HM_WILDCARD_SUFFIX) for e in entries), entries

    case = str(row.input["case"])
    path = _tool_path(tmp_path, with_uv=_FAKE_UV.get(case))
    if case == "uv missing from PATH":
        assert all(not (Path(p) / "uv").exists() for p in path.split(os.pathsep))
    bash = shutil.which("bash")
    assert bash is not None
    work = tmp_path / "work"
    work.mkdir()
    res = subprocess.run(  # noqa: S603 - fixed argv, command under test comes from our render
        [bash, "-c", cmd],
        cwd=work,
        env={"PATH": path, "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert res.returncode == row.expected["exit"], (res.returncode, res.stdout, res.stderr)
    objs = _json_objects(res.stdout)
    assert objs is not None, f"stdout is not clean JSON: {res.stdout!r}"
    assert len(objs) == row.expected["json_objects"], res.stdout
    obj = objs[0]
    assert isinstance(obj, dict)
    assert ("unavailable" in obj) is row.expected["unavailable"], obj


# ---------------------------------------------------------------------------
# AC-014 / AC-016 / AC-017 — the always-loaded world-model pointer
# ---------------------------------------------------------------------------

# (config, file, runtime, locale of the arm)
_POINTERS = [
    ("en", "CLAUDE.md", "claude-code", "en"),
    ("ko", "CLAUDE.md", "claude-code", "ko"),
    ("en", ".cursor/rules/harness.mdc", "cursor", "en"),
    ("ko", ".cursor/rules/harness.mdc", "cursor", "any"),
    ("en", "AGENTS.md", "codex", "en"),
    ("ko", "AGENTS.md", "codex", "any"),
]
_POINTER_IDS = ["claude-en", "claude-ko", "cursor-en", "cursor-ko", "codex-en", "codex-ko"]
_MAX_POINTERS = [
    ("en_max", "CLAUDE.md", "claude-code", "en"),
    ("ko_max", "CLAUDE.md", "claude-code", "ko"),
    ("en_max", ".cursor/rules/harness.mdc", "cursor", "en"),
    ("en_max", "AGENTS.md", "codex", "en"),
]
_MAX_IDS = ["claude-en-max", "claude-ko-max", "cursor-max", "codex-max"]

# ADR-006/008 routing content. Each group accepts its en or ko wording; one member must appear.
_ROUTING_GROUPS: dict[str, tuple[str, ...]] = {
    "goal": ("goal", "목표"),
    "metric": ("metric", "지표"),
    "fact": ("fact", "사실"),
    "status": ("status", "상태", "현황"),
    "unnamed": ("unnamed", "named or not", "not named", "이름을 부르지", "부르지 않아도"),
    "mid-stage": ("mid-stage", "while a stage", "during a stage", "단계 중", "단계 진행 중"),
}


def _pointer(root: Path, rel: str) -> str:
    return _section(_read(root, rel), "## World model")


def _decision_literals(locale: str) -> tuple[str, ...]:
    return {"en": ("before replying",), "ko": ("답하기 전",)}.get(
        locale, ("before replying", "답하기 전")
    )


@pytest.mark.parametrize(
    ("config", "rel", "runtime", "locale"),
    _POINTERS + _MAX_POINTERS,
    ids=_POINTER_IDS + _MAX_IDS,
)
def test_ac014_pointer_routes_unnamed(
    config: str, rel: str, runtime: str, locale: str, repo: Callable[[str], Path]
) -> None:
    name, handle, _, _ = _CONFIGS[config]
    section = _pointer(repo(config), rel)
    assert len(section) <= _POINTER_CAP, (rel, len(section))
    assert name in section
    assert _invocation(runtime, handle) in section, section
    low = section.lower()
    missing = [g for g, words in _ROUTING_GROUPS.items() if not any(w in low for w in words)]
    assert missing == [], (missing, section)
    # S10 "ordinary coding asks are not captured": the exclusion is a pinned negation literal,
    # so a pointer that ROUTES build/fix cannot pass on the bare word.
    assert _EXCLUSION_BY_LOCALE.get(locale, "not build/fix") in section, section


@pytest.mark.parametrize(("config", "rel", "runtime", "locale"), _POINTERS, ids=_POINTER_IDS)
def test_ac016_decision_capture_instructed(
    config: str, rel: str, runtime: str, locale: str, repo: Callable[[str], Path]
) -> None:
    section = _pointer(repo(config), rel)
    assert any(lit in section for lit in _decision_literals(locale)), section
    maker_runtime = "codex" if runtime == "codex" else "claude-code"
    maker_config = "cursor" if runtime == "cursor" and config == "en" else config
    maker = _maker(repo, maker_config, maker_runtime)
    assert _DECISION_RULE in maker
    resume = _section(maker, "## Resume")
    assert _RESUME_LATEST in resume, resume


@pytest.mark.parametrize(("config", "rel", "runtime", "locale"), _POINTERS, ids=_POINTER_IDS)
def test_ac017_mid_stage_aside(
    config: str, rel: str, runtime: str, locale: str, repo: Callable[[str], Path]
) -> None:
    name = _CONFIGS[config][0]
    section = _pointer(repo(config), rel)
    missing = [c for c in _POINTER_ASIDE if c not in section]
    missing += [c for c in _POINTER_ASIDE_BY_LOCALE.get(locale, ("6 lines",)) if c not in section]
    assert missing == [], (missing, section)
    opener = _POINTER_OPENER_BY_LOCALE.get(locale, "asides start `{name} —`").format(name=name)
    assert opener in section, (opener, section)
    maker_runtime = "codex" if runtime == "codex" else "claude-code"
    maker_config = "cursor" if runtime == "cursor" and config == "en" else config
    maker = _maker(repo, maker_config, maker_runtime)
    maker_name = _CONFIGS[maker_config][0]
    # The aside clause itself, not the pre-existing Voice line, must carry the opener.
    assert _MAKER_OPENER.format(name=maker_name) in maker
    missing = [c for c in _MAKER_ASIDE if c not in maker]
    assert missing == [], missing
