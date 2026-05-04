"""AI-readiness Layer-1 scoring — deterministic, evidence-anchored.

Each of 7 dimensions is composed of multiple signals; each signal is a yes/no
deterministic check producing evidence + an optional remediation action.

Layer 3 (cache_efficiency) is computed separately by `cache_diagnostics.py`.
Layer 2 (LLM-judged content quality) is computed by `llm_judge.py`.
The orchestrator in `/hm:ai-readiness` combines all three.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from harness_maker.context_lint import _count_body_lines
from harness_maker.models import Preset

# Layer-1 dimension weights (sum to 1.0 per preset).
WEIGHTS_SIDE: dict[str, float] = {
    "context_quality": 0.26,
    "guardrails": 0.21,
    "verification": 0.21,
    "workflow_clarity": 0.11,
    "memory_continuity": 0.11,
    "observability_setup": 0.10,
    "governance": 0.00,
}
WEIGHTS_PROD: dict[str, float] = {
    "context_quality": 0.21,
    "guardrails": 0.26,
    "verification": 0.21,
    "workflow_clarity": 0.11,
    "memory_continuity": 0.11,
    "observability_setup": 0.05,
    "governance": 0.05,
}

# CLAUDE.md / agent / skill body line caps (per preset). Mirrors context_lint.THRESHOLDS.
_CONTEXT_LIMITS: dict[tuple[str, str], int] = {
    ("CLAUDE.md", "Side"): 200,
    ("CLAUDE.md", "Production"): 500,
    ("agent", "Side"): 100,
    ("agent", "Production"): 200,
    ("skill", "Side"): 50,
    ("skill", "Production"): 150,
}

# Dangerous patterns that the deny list should cover.
_DANGEROUS_DENY_PATTERNS = [
    "rm",  # rm -rf
    "curl",  # curl | sh
    "Write(/etc",  # write to root config
    "Write(~/.ssh",  # write to ssh keys
]

# Dirs to skip when scanning source files
_SCAN_IGNORE = {"build", "_build", ".git", "node_modules", "__pycache__", ".venv", "target", "dist"}


class Signal(BaseModel):
    """One deterministic check contributing to a dimension score."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    passed: bool
    weight: int  # contribution to the dim score when passed (sum across all signals = 100)
    evidence: str
    action: str | None  # remediation hint when failed


class DimensionScore(BaseModel):
    """One dimension of the Layer-1 readiness composite."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str
    score: int  # 0-100, weighted sum of passed signals
    signals: list[Signal]


class ReadinessResult(BaseModel):
    """Full Layer-1 readiness output."""

    model_config = ConfigDict(strict=True, extra="forbid")

    preset: str
    dimensions: dict[str, DimensionScore]
    weights: dict[str, float]
    ceremony_penalty: float
    user_md_files: int
    composite: int  # weighted sum of dim scores, post ceremony penalty


# ── helpers ─────────────────────────────────────────────────────────────────


def _strip_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (frontmatter_dict_or_none, body)."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    fm_block = text[4:end]
    body = text[end + 5 :]
    fm: dict[str, Any] = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_json_with_optional_frontmatter(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if not text:
        return None
    if text.startswith("---\n"):
        _, text = _strip_frontmatter(text)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _signal(sig_id: str, passed: bool, weight: int, evidence: str, action: str | None) -> Signal:
    return Signal(id=sig_id, passed=passed, weight=weight, evidence=evidence, action=action)


def _score_signals(signals: list[Signal]) -> int:
    earned = sum(s.weight for s in signals if s.passed)
    return max(0, min(100, earned))


# ── stack detection (carried over from prior readiness) ─────────────────────


def _detect_stacks(project_dir: Path) -> set[str]:
    stacks: set[str] = set()
    if any((project_dir / m).exists() for m in ["pyproject.toml", "requirements.txt", "setup.py"]):
        stacks.add("python")
    if (project_dir / "pubspec.yaml").exists():
        stacks.add("dart")
    if (project_dir / "CMakeLists.txt").exists():
        stacks.add("c")
    if (project_dir / "Cargo.toml").exists():
        stacks.add("rust")
    if (project_dir / "go.mod").exists():
        stacks.add("go")
    if (project_dir / "package.json").exists():
        stacks.add("node")
    return stacks


def _has_tests_python(project_dir: Path) -> bool:
    tests_dir = project_dir / "tests"
    if not tests_dir.is_dir():
        return False
    for py in tests_dir.rglob("*.py"):
        try:
            if "def test_" in py.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False


def _has_tests_dart(project_dir: Path) -> bool:
    test_dir = project_dir / "test"
    return test_dir.is_dir() and any(test_dir.rglob("*_test.dart"))


def _has_tests_c(project_dir: Path) -> bool:
    if (project_dir / "tests").is_dir():
        return True
    scanned = 0
    for c_file in project_dir.rglob("*.c"):
        if any(part in _SCAN_IGNORE for part in c_file.parts):
            continue
        if scanned >= 100:
            break
        scanned += 1
        try:
            content = c_file.read_text(encoding="utf-8", errors="ignore")
            if "ZTEST(" in content or "TEST(" in content or "test_" in c_file.name:
                return True
        except OSError:
            continue
    return False


def _has_tests_rust(project_dir: Path) -> bool:
    tests_dir = project_dir / "tests"
    if tests_dir.is_dir() and any(tests_dir.glob("*.rs")):
        return True
    scanned = 0
    for rs_file in project_dir.rglob("*.rs"):
        if any(part in _SCAN_IGNORE for part in rs_file.parts):
            continue
        if scanned >= 100:
            break
        scanned += 1
        try:
            if "#[test]" in rs_file.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False


def _has_tests_go(project_dir: Path) -> bool:
    return any(
        f
        for f in project_dir.rglob("*_test.go")
        if not any(part in _SCAN_IGNORE for part in f.parts)
    )


def _has_tests_node(project_dir: Path) -> bool:
    pkg = project_dir / "package.json"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        if "test" in data.get("scripts", {}):
            return True
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    patterns = ("*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts")
    return any(
        f
        for pat in patterns
        for f in project_dir.rglob(pat)
        if not any(part in _SCAN_IGNORE for part in f.parts)
    )


_STACK_TESTERS = {
    "python": _has_tests_python,
    "dart": _has_tests_dart,
    "c": _has_tests_c,
    "rust": _has_tests_rust,
    "go": _has_tests_go,
    "node": _has_tests_node,
}


# ── dimension computers ─────────────────────────────────────────────────────


def _dim_context_quality(project_dir: Path, preset: Preset) -> DimensionScore:
    """CLAUDE.md presence + line limits + agent/skill structural quality."""
    signals: list[Signal] = []
    claude_md = project_dir / "CLAUDE.md"
    claude_limit = _CONTEXT_LIMITS[("CLAUDE.md", preset.value)]
    if claude_md.is_file():
        body_lines = _count_body_lines(_read_text(claude_md))
        signals.append(
            _signal(
                "claude_md_present",
                True,
                30,
                f"CLAUDE.md exists ({body_lines} body lines)",
                None,
            )
        )
        signals.append(
            _signal(
                "claude_md_within_limit",
                body_lines <= claude_limit,
                15,
                f"{body_lines} lines vs {claude_limit} limit ({preset.value})",
                f"Trim CLAUDE.md to ≤ {claude_limit} lines (split into skills or imports)"
                if body_lines > claude_limit
                else None,
            )
        )
    else:
        signals.append(
            _signal(
                "claude_md_present",
                False,
                30,
                "CLAUDE.md is missing",
                "Create CLAUDE.md with tech stack, build commands, and code conventions",
            )
        )
        signals.append(
            _signal(
                "claude_md_within_limit",
                False,
                15,
                "CLAUDE.md does not exist",
                None,
            )
        )

    readme = project_dir / "README.md"
    signals.append(
        _signal(
            "readme_present",
            readme.is_file(),
            10,
            "README.md exists" if readme.is_file() else "README.md missing",
            None if readme.is_file() else "Add README.md describing the project",
        )
    )

    # Agent prompt line limits — pass iff every agent file is within limits.
    agent_dir = project_dir / ".claude" / "agents"
    agent_limit = _CONTEXT_LIMITS[("agent", preset.value)]
    agents = list(agent_dir.glob("*.md")) if agent_dir.is_dir() else []
    over_agents = [a.name for a in agents if _count_body_lines(_read_text(a)) > agent_limit]
    signals.append(
        _signal(
            "agents_within_limit",
            not over_agents,
            15,
            (
                f"All {len(agents)} agent prompts ≤ {agent_limit} lines"
                if not over_agents
                else f"{len(over_agents)} agent prompts exceed {agent_limit} lines: "
                + ", ".join(over_agents[:3])
            ),
            (None if not over_agents else f"Trim these agent prompts to ≤ {agent_limit} lines"),
        )
    )

    # Skill SKILL.md line limits.
    skill_dir = project_dir / ".claude" / "skills"
    skill_limit = _CONTEXT_LIMITS[("skill", preset.value)]
    skills = list(skill_dir.rglob("SKILL.md")) if skill_dir.is_dir() else []
    over_skills = [s.parent.name for s in skills if _count_body_lines(_read_text(s)) > skill_limit]
    signals.append(
        _signal(
            "skills_within_limit",
            not over_skills,
            15,
            (
                f"All {len(skills)} SKILL.md files ≤ {skill_limit} lines"
                if not over_skills
                else f"{len(over_skills)} SKILL.md files exceed {skill_limit} lines: "
                + ", ".join(over_skills[:3])
            ),
            (None if not over_skills else f"Trim these SKILL.md files to ≤ {skill_limit} lines"),
        )
    )

    # Frontmatter validity for agents.
    bad_fm_agents: list[str] = []
    for a in agents:
        fm, _ = _strip_frontmatter(_read_text(a))
        if fm is None or "name" not in fm or "description" not in fm:
            bad_fm_agents.append(a.name)
    signals.append(
        _signal(
            "agent_frontmatter_valid",
            not bad_fm_agents,
            15,
            (
                "All agents have valid frontmatter (name + description)"
                if not bad_fm_agents
                else f"{len(bad_fm_agents)} agents missing frontmatter fields"
            ),
            (None if not bad_fm_agents else "Add `name:` and `description:` to agent frontmatter"),
        )
    )

    return DimensionScore(name="context_quality", score=_score_signals(signals), signals=signals)


def _dim_guardrails(project_dir: Path) -> DimensionScore:
    """Hooks defined + permissions deny list density."""
    signals: list[Signal] = []
    claude = project_dir / ".claude"

    hooks_path = claude / "hooks" / "hooks.json"
    hooks_data = _read_json_with_optional_frontmatter(hooks_path) if hooks_path.exists() else None
    hook_count = 0
    if isinstance(hooks_data, dict):
        for events in hooks_data.values():
            if isinstance(events, list):
                for h in events:
                    if isinstance(h, dict) and h.get("hooks"):
                        hook_count += len(h["hooks"]) if isinstance(h["hooks"], list) else 0

    signals.append(
        _signal(
            "hooks_json_present",
            hooks_path.exists(),
            25,
            "hooks.json exists" if hooks_path.exists() else "hooks.json missing",
            None if hooks_path.exists() else "Add .claude/hooks/hooks.json with at least telemetry",
        )
    )
    signals.append(
        _signal(
            "hooks_defined",
            hook_count > 0,
            25,
            f"{hook_count} hook(s) defined" if hook_count else "No hooks defined",
            None
            if hook_count > 0
            else "Define PreToolUse/PostToolUse hooks (e.g., secret scan, telemetry)",
        )
    )

    settings_path = claude / "settings.json"
    settings = _read_json_with_optional_frontmatter(settings_path)
    perms = settings.get("permissions") if isinstance(settings, dict) else None
    deny = perms.get("deny") if isinstance(perms, dict) else None
    deny_list: list[str] = deny if isinstance(deny, list) else []

    signals.append(
        _signal(
            "permissions_deny_present",
            len(deny_list) > 0,
            20,
            f"settings.json permissions.deny has {len(deny_list)} pattern(s)"
            if deny_list
            else "settings.json permissions.deny is empty or missing",
            None
            if deny_list
            else "Add settings.json `permissions.deny` blocking dangerous Bash patterns",
        )
    )

    deny_text = " ".join(str(p) for p in deny_list).lower()
    matched = [p for p in _DANGEROUS_DENY_PATTERNS if p.lower() in deny_text]
    cov_evidence = (
        f"Deny patterns cover {len(matched)}/{len(_DANGEROUS_DENY_PATTERNS)} dangerous patterns"
        if matched
        else "Deny list does not cover dangerous patterns"
    )
    signals.append(
        _signal(
            "deny_covers_dangerous",
            len(matched) >= 3,
            15,
            cov_evidence,
            None if len(matched) >= 3 else "Block rm -rf, curl|sh, writes to /etc and ~/.ssh",
        )
    )

    sec_dir = claude / "observability" / "security"
    high_count = 0
    if sec_dir.is_dir():
        for f in sec_dir.glob("findings-*.jsonl"):
            try:
                for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if '"severity": "high"' in line or '"severity":"high"' in line:
                        high_count += 1
            except OSError:
                continue
    sec_action = (
        None
        if high_count == 0
        else f"Resolve {high_count} high-severity finding(s) under .claude/observability/security/"
    )
    signals.append(
        _signal(
            "no_high_security_findings",
            high_count == 0,
            15,
            f"{high_count} high-severity security finding(s) recorded"
            if high_count
            else "No high-severity security findings (or not yet scanned)",
            sec_action,
        )
    )

    return DimensionScore(name="guardrails", score=_score_signals(signals), signals=signals)


def _dim_verification(project_dir: Path) -> DimensionScore:
    """Tests for detected stack + CI + verify-before-completion."""
    signals: list[Signal] = []
    stacks = _detect_stacks(project_dir)
    signals.append(
        _signal(
            "stack_detected",
            bool(stacks),
            20,
            f"Detected stacks: {', '.join(sorted(stacks))}"
            if stacks
            else "No language stack detected",
            None if stacks else "Add a manifest (pyproject.toml, package.json, Cargo.toml, etc.)",
        )
    )

    has_tests = bool(stacks) and any(
        _STACK_TESTERS[s](project_dir) for s in stacks if s in _STACK_TESTERS
    )
    signals.append(
        _signal(
            "tests_present",
            has_tests,
            30,
            "Tests detected for project's stack" if has_tests else "No tests detected",
            None if has_tests else "Add tests for the detected stack",
        )
    )

    workflows_dir = project_dir / ".github" / "workflows"
    workflow_files = list(workflows_dir.glob("*.yml")) if workflows_dir.is_dir() else []
    signals.append(
        _signal(
            "ci_workflow_present",
            bool(workflow_files),
            20,
            f"{len(workflow_files)} workflow file(s) in .github/workflows/"
            if workflow_files
            else ".github/workflows/ has no .yml files",
            None
            if workflow_files
            else "Add a GitHub Actions workflow that runs lint + tests on PR",
        )
    )

    ci_invokes_tests = False
    test_keywords = ("pytest", "cargo test", "go test", "npm test", "pnpm test", "flutter test")
    for wf in workflow_files:
        try:
            content = wf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(kw in content for kw in test_keywords):
            ci_invokes_tests = True
            break
    signals.append(
        _signal(
            "ci_invokes_tests",
            ci_invokes_tests,
            15,
            "CI workflow runs a recognized test command"
            if ci_invokes_tests
            else "No CI workflow invokes a recognized test command",
            None if ci_invokes_tests else "Wire your test command into the CI workflow",
        )
    )

    verify_skill = project_dir / ".claude" / "skills" / "verify-before-completion" / "SKILL.md"
    signals.append(
        _signal(
            "verify_skill_installed",
            verify_skill.is_file(),
            15,
            "verify-before-completion skill installed"
            if verify_skill.is_file()
            else "verify-before-completion skill missing",
            None
            if verify_skill.is_file()
            else "Run /hm:make to install the verify-before-completion skill",
        )
    )

    return DimensionScore(name="verification", score=_score_signals(signals), signals=signals)


def _dim_workflow_clarity(project_dir: Path) -> DimensionScore:
    """Commands, fused workflows, harness.yaml workflow definitions."""
    signals: list[Signal] = []
    cmd_dir = project_dir / ".claude" / "commands" / "hm"
    commands = list(cmd_dir.glob("*.md")) if cmd_dir.is_dir() else []
    signals.append(
        _signal(
            "commands_present",
            bool(commands),
            30,
            f"{len(commands)} /hm: command(s)" if commands else "No /hm: commands found",
            None if commands else "Run /hm:make to install the standard /hm: commands",
        )
    )

    # Atomic stage commands have hyphen-free names; fused workflows have multi-stage names.
    atomic_stages = {"research", "spec", "plan", "execute", "review", "wrapup", "verify"}
    fused = [c for c in commands if c.stem not in atomic_stages and "-" in c.stem]
    signals.append(
        _signal(
            "fused_workflow_present",
            bool(fused),
            30,
            f"{len(fused)} fused workflow(s): " + ", ".join(c.stem for c in fused[:3])
            if fused
            else "No fused workflows defined",
            None
            if fused
            else "Define fused workflows in harness.yaml (e.g., exec-rev, exec-rev-wrap)",
        )
    )

    cmds_with_provenance = 0
    for c in commands:
        fm, _ = _strip_frontmatter(_read_text(c))
        if fm and "content_hash" in fm:
            cmds_with_provenance += 1
    all_have_provenance = bool(commands) and cmds_with_provenance == len(commands)
    signals.append(
        _signal(
            "commands_have_provenance",
            all_have_provenance,
            20,
            f"{cmds_with_provenance}/{len(commands)} commands have provenance frontmatter"
            if commands
            else "No commands to check",
            None
            if all_have_provenance or not commands
            else "Re-render commands via /hm:make to add provenance frontmatter",
        )
    )

    harness = project_dir / ".claude" / "harness.yaml"
    has_workflows = False
    if harness.is_file():
        text = _read_text(harness)
        has_workflows = "workflows:" in text and "default_workflow:" in text
    signals.append(
        _signal(
            "harness_workflows_defined",
            has_workflows,
            20,
            "harness.yaml defines workflows + default_workflow"
            if has_workflows
            else "harness.yaml missing workflow definitions",
            None if has_workflows else "Add `workflows:` and `default_workflow:` to harness.yaml",
        )
    )

    return DimensionScore(name="workflow_clarity", score=_score_signals(signals), signals=signals)


def _dim_memory_continuity(project_dir: Path) -> DimensionScore:
    """failures.md, wiki.md, harness.yaml memory.dir config."""
    signals: list[Signal] = []
    memory_dir = project_dir / ".claude" / "memory"
    failures = memory_dir / "failures.md"
    wiki = memory_dir / "wiki.md"

    signals.append(
        _signal(
            "failures_md_present",
            failures.is_file(),
            30,
            "memory/failures.md exists" if failures.is_file() else "memory/failures.md missing",
            None
            if failures.is_file()
            else "Run /hm:make; document each post-mortem lesson in memory/failures.md",
        )
    )

    has_real_lessons = False
    if failures.is_file():
        text = _read_text(failures)
        body = _strip_frontmatter(text)[1]
        non_empty_lines = [
            line
            for line in body.splitlines()
            if line.strip() and not line.lstrip().startswith("<!--")
        ]
        has_real_lessons = len(non_empty_lines) > 10
    signals.append(
        _signal(
            "failures_md_has_content",
            has_real_lessons,
            30,
            "failures.md contains accumulated lessons (>10 lines)"
            if has_real_lessons
            else "failures.md is empty or stub",
            None if has_real_lessons else "Append real failure lessons after each incident",
        )
    )

    signals.append(
        _signal(
            "wiki_md_present",
            wiki.is_file(),
            20,
            "memory/wiki.md exists" if wiki.is_file() else "memory/wiki.md missing",
            None if wiki.is_file() else "Run /hm:make to install memory/wiki.md scaffolding",
        )
    )

    harness = project_dir / ".claude" / "harness.yaml"
    has_memory_config = "memory:" in _read_text(harness) if harness.is_file() else False
    signals.append(
        _signal(
            "harness_memory_configured",
            has_memory_config,
            20,
            "harness.yaml has memory configuration"
            if has_memory_config
            else "harness.yaml lacks memory configuration",
            None if has_memory_config else "Add `memory:` config to harness.yaml",
        )
    )

    return DimensionScore(name="memory_continuity", score=_score_signals(signals), signals=signals)


def _dim_observability_setup(project_dir: Path) -> DimensionScore:
    """observability dir + metrics.jsonl + dashboard.md."""
    signals: list[Signal] = []
    obs = project_dir / ".claude" / "observability"
    metrics = obs / "metrics.jsonl"
    dashboard = obs / "dashboard.md"

    signals.append(
        _signal(
            "observability_dir_present",
            obs.is_dir(),
            25,
            ".claude/observability/ exists" if obs.is_dir() else ".claude/observability/ missing",
            None if obs.is_dir() else "Run /hm:make to scaffold the observability directory",
        )
    )
    signals.append(
        _signal(
            "metrics_jsonl_present",
            metrics.is_file(),
            25,
            "metrics.jsonl exists" if metrics.is_file() else "metrics.jsonl missing",
            None if metrics.is_file() else "Install the PostToolUse telemetry hook (run /hm:make)",
        )
    )
    signals.append(
        _signal(
            "dashboard_md_present",
            dashboard.is_file(),
            25,
            "dashboard.md exists" if dashboard.is_file() else "dashboard.md missing",
            None if dashboard.is_file() else "Run /hm:ai-readiness to render the dashboard",
        )
    )

    sample_size = 0
    if metrics.is_file():
        try:
            sample_size = sum(1 for line in _read_text(metrics).splitlines() if line.strip())
        except OSError:
            sample_size = 0
    has_samples = sample_size >= 5
    signals.append(
        _signal(
            "metrics_has_samples",
            has_samples,
            25,
            f"metrics.jsonl has {sample_size} entr{'y' if sample_size == 1 else 'ies'}"
            if metrics.is_file()
            else "no metrics.jsonl",
            None if has_samples else "Use Claude Code for ≥ 5 turns to accumulate telemetry",
        )
    )

    return DimensionScore(
        name="observability_setup", score=_score_signals(signals), signals=signals
    )


def _dim_governance(project_dir: Path, preset: Preset) -> DimensionScore:
    """Side preset: weight-0 (irrelevant). Production: ADR + CONTRIBUTING."""
    signals: list[Signal] = []
    if preset == Preset.SIDE:
        signals.append(
            _signal(
                "side_governance_skipped",
                True,
                100,
                "Governance not required for Side preset (weight 0)",
                None,
            )
        )
        return DimensionScore(name="governance", score=100, signals=signals)

    adr_dir = project_dir / "docs" / "adr"
    has_adr = adr_dir.is_dir() and any(adr_dir.glob("*.md"))
    signals.append(
        _signal(
            "adr_present",
            has_adr,
            50,
            "ADR documents found in docs/adr/" if has_adr else "No ADRs in docs/adr/",
            None if has_adr else "Document architecture decisions under docs/adr/",
        )
    )

    contributing = (project_dir / "CONTRIBUTING.md").is_file() or (
        project_dir / "docs" / "CONTRIBUTING.md"
    ).is_file()
    signals.append(
        _signal(
            "contributing_present",
            contributing,
            50,
            "CONTRIBUTING.md exists" if contributing else "CONTRIBUTING.md missing",
            None if contributing else "Add CONTRIBUTING.md (or docs/CONTRIBUTING.md)",
        )
    )

    return DimensionScore(name="governance", score=_score_signals(signals), signals=signals)


# ── ceremony penalty (carried over) ─────────────────────────────────────────


def _count_user_md_files(claude_dir: Path) -> int:
    """Count .md files in .claude/ without harness-maker provenance frontmatter."""
    if not claude_dir.is_dir():
        return 0
    count = 0
    for f in claude_dir.rglob("*.md"):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            count += 1
            continue
        if not (text.startswith("---\n") and "content_hash:" in text[:500]):
            count += 1
    return count


# ── public API ──────────────────────────────────────────────────────────────


def compute_readiness(project_dir: Path, preset: Preset) -> ReadinessResult:
    """Compute Layer-1 readiness across 7 deterministic dimensions.

    Layer 3 (cache_efficiency) and Layer 2 (LLM-judged content quality) are
    folded in by the orchestrator at /hm:ai-readiness, not here.
    """
    weights = WEIGHTS_SIDE if preset == Preset.SIDE else WEIGHTS_PROD

    dims: dict[str, DimensionScore] = {
        "context_quality": _dim_context_quality(project_dir, preset),
        "guardrails": _dim_guardrails(project_dir),
        "verification": _dim_verification(project_dir),
        "workflow_clarity": _dim_workflow_clarity(project_dir),
        "memory_continuity": _dim_memory_continuity(project_dir),
        "observability_setup": _dim_observability_setup(project_dir),
        "governance": _dim_governance(project_dir, preset),
    }

    weighted = sum(dims[k].score * weights[k] for k in weights)

    claude_dir = project_dir / ".claude"
    user_md = _count_user_md_files(claude_dir)
    target = 10 if preset == Preset.SIDE else 15
    ceremony_penalty = max(0.0, min(15.0, max(0, user_md - target) * 1.5))

    composite = max(0, min(100, int(weighted - ceremony_penalty)))
    return ReadinessResult(
        preset=preset.value,
        dimensions=dims,
        weights=weights,
        ceremony_penalty=ceremony_penalty,
        user_md_files=user_md,
        composite=composite,
    )
