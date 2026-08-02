"""AI-readiness Layer-1 scoring — deterministic, evidence-anchored.

Each of 7 dimensions is composed of multiple signals; each signal is a yes/no
deterministic check producing evidence + an optional remediation action.

Layer 3 (cache_efficiency) is computed separately by `cache_diagnostics.py`.
Layer 2 (LLM-judged content quality) is computed by `llm_judge.py`.
The orchestrator in `/hm:ai-readiness` combines all three.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from harness_maker._metrics_io import _candidate_files
from harness_maker.context_lint import _count_body_lines
from harness_maker.models import Preset

# Layer-1 dimension weights (sum to 1.0 per preset).
# model_routing is weight 0 (advisory per ADR-010) — surfaces signals/actions
# in the dashboard without changing the composite score.
WEIGHTS_SIDE: dict[str, float] = {
    "context_quality": 0.26,
    "guardrails": 0.21,
    "verification": 0.21,
    "workflow_clarity": 0.11,
    "memory_continuity": 0.11,
    "observability_setup": 0.10,
    "governance": 0.00,
    "model_routing": 0.00,
}
WEIGHTS_PROD: dict[str, float] = {
    "context_quality": 0.21,
    "guardrails": 0.26,
    "verification": 0.21,
    "workflow_clarity": 0.11,
    "memory_continuity": 0.11,
    "observability_setup": 0.05,
    "governance": 0.05,
    "model_routing": 0.00,
}

# CLAUDE.md / agent / skill body line caps (per preset). Matches the canonical
# CLAUDE.md Context Lint section and context_lint.THRESHOLDS (aligned 0.28.x —
# context_lint's Side rows were raised from 100/50 to 150/100 to agree; agent and
# skill rows raised to a flat 300 in 0.45.0, see context_lint.THRESHOLDS).
_CONTEXT_LIMITS: dict[tuple[str, str], int] = {
    ("CLAUDE.md", "Side"): 200,
    ("CLAUDE.md", "Production"): 500,
    ("agent", "Side"): 300,
    ("agent", "Production"): 300,
    ("skill", "Side"): 300,
    ("skill", "Production"): 300,
}

# Dangerous patterns the deny list should cover, when the user opts in.
#
# These must name rule shapes Claude Code actually MATCHES — the pre-0.40 list
# scored `Write(/etc` and `curl` (as in `Bash(curl * | sh)`), both of which are
# accepted-but-never-enforced, so this signal passed on a deny list that stopped
# nothing. `permission_syntax.is_matchable_rule` is the shared oracle; the
# template and this list are kept in lockstep by test_readiness_deny_lockstep.py,
# which asserts every pattern below matches a rule the template really renders.
#
# `curl|sh` detection moved to `permission_gate`'s PreToolUse hook (ADR-003) —
# no rule shape can express it, so it is deliberately not scored here.
_DANGEROUS_DENY_PATTERNS = [
    "rm",  # rm -rf
    "Edit(/etc",  # write to root config
    "Edit(~/.ssh",  # write to ssh keys
    "Edit(~/.aws",  # write to cloud credentials
]

# Tolerate exactly one gap, derived from the list rather than hardcoded: a bare
# `>= 3` silently becomes "all required" the moment the list shrinks to 3.
_DENY_COVERAGE_MIN = len(_DANGEROUS_DENY_PATTERNS) - 1

# ADR-006: signals that fail on fresh install for reasons /hm:make cannot
# resolve in a single shot — either because the artefact only appears after
# real Claude Code use (telemetry) or because it requires user authoring
# (CI workflow, ADR notes, CONTRIBUTING). Used by:
#   - Phase 4 integration test allowlist (was the ONLY consumer in 0.17.0).
#   - PLAN-fresh-install-p0-calibration (0.19.3): the user-facing priority
#     emitter `improvement._extract_layer1_actions` now consults these subsets
#     to suppress auto-resolve signals while samples < 5 and to override
#     user-author signals to "P2" regardless of weight.
#
# TELEMETRY_AUTO_RESOLVE_SIGNALS:
#   Samples-based TTL — once `metrics_has_samples.passed` becomes True
#   (samples ≥ 5) the suppression lifts and these surface normally as P0,
#   so a real telemetry regression at steady state still alerts.
#
# USER_AUTHOR_SIGNALS:
#   No TTL — these never auto-resolve; emitter demotes them to P2 to surface
#   them as aspirational items rather than urgent alerts.
TELEMETRY_AUTO_RESOLVE_SIGNALS: frozenset[str] = frozenset(
    {
        "metrics_jsonl_present",
        "metrics_has_samples",
    }
)

USER_AUTHOR_SIGNALS: frozenset[str] = frozenset(
    {
        "ci_workflow_present",
        "adr_present",
        "contributing_present",
    }
)

# Backwards-compatible union — preserved for the Phase 4 integration test
# allowlist and any other consumer that imports the original symbol.
INTENDED_P0_SIGNALS: frozenset[str] = TELEMETRY_AUTO_RESOLVE_SIGNALS | USER_AUTHOR_SIGNALS

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
    # ADR-004 (PLAN-multisession-10-fleet-hardening): a failed hard-gate floors the
    # dimension score to 0 regardless of additive weight — for invariants that must
    # fail health even when the dimension's passed-weights already cap at 100.
    hard_gate: bool = False


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


def _signal(
    sig_id: str,
    passed: bool,
    weight: int,
    evidence: str,
    action: str | None,
    *,
    hard_gate: bool = False,
) -> Signal:
    return Signal(
        id=sig_id,
        passed=passed,
        weight=weight,
        evidence=evidence,
        action=action,
        hard_gate=hard_gate,
    )


def _score_signals(signals: list[Signal]) -> int:
    # ADR-004: a failed hard-gate signal floors the dimension to 0 — below any
    # composite green cutoff — so a critical degraded invariant cannot be masked by
    # the dimension's >100 additive passed-weight sum (capped at 100).
    if any(s.hard_gate and not s.passed for s in signals):
        return 0
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


def _dim_guardrails(project_dir: Path, *, session_id: str | None = None) -> DimensionScore:
    """Hooks defined + permissions deny list density.

    ``session_id`` is TRI-STATE and the three states must stay distinguishable
    (PLAN-sessionid-env-propagation ADR-001): ``None`` = the caller never wired the
    probe, ``""`` = the caller wired it and the value was genuinely absent, non-empty =
    healthy. Collapsing ``None`` into ``""`` re-creates the defect this parameter exists
    to remove.
    """
    signals: list[Signal] = []
    claude = project_dir / ".claude"

    # Claude Code reads project hooks ONLY from settings files — `.claude/hooks/hooks.json`
    # is never loaded (PLAN-permission-deny-and-hooks-wiring; that path is plugin-bundle-only).
    # These signals MUST read the file that actually governs behavior: scoring the dead file
    # let a harness with no live hooks read healthy, which is the degradation
    # `sessionid_envfile_registered` exists to detect.
    hooks_path = claude / "settings.json"
    hooks_data = _read_json_with_optional_frontmatter(hooks_path) if hooks_path.exists() else None
    # The absent case is now "settings.json has no `hooks` key" — a harness with NO hooks —
    # NOT "the file is missing". The old signals were written `(not hooks_path.exists()) or …`,
    # so retiring hooks.json would have made them pass forever, for every project
    # (2026-06-08 "absent-case = feature black hole"). `has_hooks` replaces that shape.
    has_hooks = isinstance(hooks_data, dict) and isinstance(hooks_data.get("hooks"), dict)
    hook_count = 0
    if isinstance(hooks_data, dict):
        # Rendered format: {"hooks": {"PostToolUse": [...]}, "preset": "..."}
        # Legacy flat format: {"PostToolUse": [...]}
        # Only the `hooks` key counts. The old code fell back to treating the whole
        # document as the hook section (a legacy flat hooks.json shape); against
        # settings.json that would scan `permissions`/`preset` as if they were events.
        hook_section = hooks_data.get("hooks") if has_hooks else {}
        for events in hook_section.values():  # type: ignore[union-attr]
            if isinstance(events, list):
                for h in events:
                    if isinstance(h, dict) and h.get("hooks"):
                        hook_count += len(h["hooks"]) if isinstance(h["hooks"], list) else 0

    signals.append(
        _signal(
            "hooks_json_present",
            has_hooks,
            25,
            "settings.json has a `hooks` key"
            if has_hooks
            else "settings.json has no `hooks` key — Claude Code loads no project hooks",
            None
            if has_hooks
            else "Re-render with /harness-maker:make --update — hooks live in "
            ".claude/settings.json, not .claude/hooks/hooks.json (which Claude Code never reads)",
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

    # Loud smoke (PLAN-loop-marker-session-scoping P5): a rendered hooks.json that
    # does NOT register the `sessionid_envfile` SessionStart hook silently degrades
    # /hm:loop session-scoping (HM_SESSION_ID never set → parallel loops fall back
    # to the session-blind global marker). N-A (passes) when hooks.json is absent —
    # Phase 4 — there is NO fail-open arm here, deliberately.
    #
    # The old shape was `(not hooks_path.exists()) or (…)`: it passed when hooks.json was
    # absent, on the theory that `hooks_json_present` owned that case and this signal
    # should only judge a stale render. Retiring hooks.json would have turned that into
    # "passes forever, for every project" — a smoke alarm wired to always-quiet
    # (2026-06-08 "absent-case = feature black hole").
    #
    # Porting it to `not has_hooks` would preserve the same hole under a new name: after
    # Phase 4 an absent `hooks` key does not mean "nothing to judge yet", it means the
    # harness has NO live hooks — exactly the degradation this signal exists to detect.
    # So: no hooks ⇒ the SessionStart hook is not registered ⇒ FAIL. Two signals firing on
    # one root cause is the correct redundancy for a detector CLAUDE.md calls the loud
    # smoke against silent degradation.
    sessionid_registered = has_hooks and (
        "sessionid_envfile" in json.dumps(hooks_data.get("hooks"))  # type: ignore[union-attr]
    )
    signals.append(
        _signal(
            "sessionid_envfile_registered",
            sessionid_registered,
            15,
            "SessionStart sessionid_envfile hook registered (loop session-scoping live)"
            if sessionid_registered
            else "hooks.json missing the sessionid_envfile SessionStart hook — "
            "/hm:loop session-scoping is silently degraded",
            None
            if sessionid_registered
            else "Re-render with /hm:make --update so SessionStart registers "
            "harness_maker.hooks.sessionid_envfile (sets HM_SESSION_ID for /hm:loop)",
        )
    )

    # Loud smoke (PLAN-autopilot-config-surface ADR-003/P6): when
    # autonomy.autopilot_persistent is committed true, a stale render that lost the
    # autopilot_autoarm SessionStart hook means autopilot will NOT actually persist across
    # sessions (silent degradation — the user re-arms manually, defeating the feature). N-A
    # (passes, no penalty) when persistence is off or hooks.json is absent — an intentional
    # opt-out is a config choice, not a missing guardrail (permissions_deny N-A precedent).
    _autopilot_persistent = False
    _ap_hy = claude / "harness.yaml"
    if _ap_hy.is_file():
        try:
            from harness_maker.io_utils import load_harness_yaml as _lhy_ap

            _ap_cfg = _lhy_ap(_ap_hy)
            _ap_autonomy = _ap_cfg.get("autonomy") if isinstance(_ap_cfg, dict) else None
            if isinstance(_ap_autonomy, dict):
                _autopilot_persistent = _ap_autonomy.get("autopilot_persistent") is True
        except Exception:  # noqa: BLE001 — degrade to N-A, never crash readiness
            _autopilot_persistent = False
    # N-A (passes) when persistence is off OR no hooks.json exists at all — the
    # `hooks_json_present` signal owns the absent-hooks.json case, so this smoke must not
    # double-penalize a partial harness that never rendered hooks.json (mirrors the
    # `sessionid_envfile_registered` `not hooks_path.exists()` precedent). It fires only on a
    # stale render that HAS hooks.json but dropped the autoarm hook.
    # `not _autopilot_persistent` is a genuine N/A — the hook is only load-bearing for that
    # config — but "no hooks at all" is NOT (see sessionid_registered's note).
    autoarm_ok = (not _autopilot_persistent) or (
        has_hooks and "autopilot_autoarm" in json.dumps(hooks_data.get("hooks"))  # type: ignore[union-attr]
    )
    signals.append(
        _signal(
            "autopilot_autoarm_registered",
            autoarm_ok,
            # weight=0 (display-only, like the other advisory guardrail signals): this is a
            # narrow opt-in smoke that must SURFACE loudly when degraded but must NOT dock the
            # composite or perturb the "guardrail signals sum to 100" budget (a non-zero weight
            # inflated the empty-project score). hard_gate=False — visibility, not gating.
            0,
            "autopilot_persistent off (N-A) or autopilot_autoarm SessionStart hook registered"
            if autoarm_ok
            else "autonomy.autopilot_persistent is true but hooks.json lacks the "
            "autopilot_autoarm SessionStart hook — autopilot will NOT persist across sessions",
            None
            if autoarm_ok
            else "Re-render with /hm:make --update so SessionStart registers "
            "harness_maker.hooks.autopilot_autoarm (re-arms the marker each session)",
        )
    )

    # Does the delegation that is CONFIGURED actually fire? (PLAN-wrapup-context-carry
    # ADR-006.) `delegation.stages` named wrapup for four months while the dispatch
    # happened in 2 of 16 measured runs, and nothing surfaced it: the brief was
    # derivable, the render was correct, and every test was green. The ledger's dispatch
    # rows are the only observation that distinguishes "configured" from "working".
    #
    # Weight 0, like the other advisory guardrail signals: `_score_signals` sums the
    # weights of PASSED signals, so a failing weight-0 signal is score-neutral, and the
    # dimension's "weights sum to 100" budget is untouched — adding a weighted signal
    # would re-score every existing harness and read as a regression the user did not cause.
    _delegation_stages: list[str] = []
    # Defaults to the shipped default (True) so a harness.yaml that predates the key is not
    # reported as structurally broken on the strength of an absent field.
    _dl_feature_branch = True
    _dl_hy = claude / "harness.yaml"
    if _dl_hy.is_file():
        try:
            from harness_maker.io_utils import load_harness_yaml as _lhy_dl

            _dl_cfg = _lhy_dl(_dl_hy)
            _dl_block = _dl_cfg.get("delegation") if isinstance(_dl_cfg, dict) else None
            if isinstance(_dl_block, dict) and isinstance(_dl_block.get("stages"), list):
                _delegation_stages = [
                    str(s).strip().lower() for s in _dl_block["stages"] if str(s).strip()
                ]
            _dl_wt = _dl_cfg.get("worktree") if isinstance(_dl_cfg, dict) else None
            if isinstance(_dl_wt, dict) and "feature_branch_workflow" in _dl_wt:
                _dl_feature_branch = _dl_wt.get("feature_branch_workflow") is not False
        except Exception:  # noqa: BLE001 — degrade to N-A, never crash readiness
            _delegation_stages = []

    if "wrapup" not in _delegation_stages:
        # The absent case, decided rather than fallen through: a harness that never opted
        # in must not accrue an action item for a feature it does not use.
        _dl_passed, _dl_evidence, _dl_action = (
            True,
            "delegation.stages does not name wrapup (N-A)",
            None,
        )
    else:
        from harness_maker import delegation_ledger as _dl

        # Resolve the base FIRST — both writers do (`wrapup_brief` via `resolve_base_root`,
        # `wrapup_receipt` via `memory_md._base_root`), because `.claude/observability/` is
        # gitignored churn that exists only at the base while `harness.yaml` is tracked and
        # therefore present in every worktree checkout. Reading the raw `project_dir` inside
        # a worktree would pair "wrapup is delegated" with an absent ledger and report
        # `no-rows` on a harness that is dispatching correctly — the same base-vs-worktree
        # asymmetry this module was written to remove, re-introduced on the read side.
        from harness_maker.memory_md import _base_root as _dl_base

        # `stage=` is REQUIRED, not defaulted. `verify` is delegatable too, so a second
        # signal added later that omitted it would silently report the wrapup verdict under
        # a verify label — the failure mode this whole work unit is about. A required
        # keyword costs nothing at one call site and makes the omission a type error.
        _dl_verdict = _dl.dispatch_verdict(_dl.read_rows(_dl_base(project_dir)), stage="wrapup")
        _dl_passed = _dl_verdict in ("ok", "unavailable-only")
        if _dl_verdict == "no-rows":
            # "no invocation with a readable timestamp", not "no invocation": the arm is
            # also reached when rows exist but none of their timestamps parse, and calling
            # that an empty ledger would send the reader looking for the wrong thing.
            _dl_evidence = (
                "wrapup delegation is configured but no invocation with a readable "
                "timestamp is recorded yet"
            )
            # Distinct from the arm below BY DESIGN, and AC-007 asserts the inequality:
            # "never run" and "runs but never dispatches" have different remedies, and the
            # action string is the only surface a user ever sees.
            _dl_action = (
                "Run /hm:wrapup once so the delegation ledger "
                "(.claude/observability/delegation.jsonl) gets its first rows"
            )
        elif _dl_verdict == "brief-degrading" and not _dl_feature_branch:
            # `derive_brief` resolves a task branch (`hm/<slug>`); with the per-task
            # feature-branch workflow off there is never one, so every brief degrades
            # STRUCTURALLY and delegation cannot fire at all. Keep it failing — a silent
            # pass would hide that the feature is dead — but name the remedy the user can
            # actually perform. "The brief is not derivable" would be permanently true and
            # permanently unactionable, which is the `absent-case = feature black hole`
            # shape the `unavailable-only` arm already exists to avoid.
            _dl_evidence = (
                "delegation is configured but worktree.feature_branch_workflow is off — "
                "the brief has no task branch to resolve, so it degrades on every run"
            )
            _dl_action = (
                "Set worktree.feature_branch_workflow: true (delegation derives its brief "
                "from an hm/<slug> task branch), or clear delegation.stages if this harness "
                "is not using the per-task worktree model"
            )
        elif _dl_verdict == "brief-degrading":
            # A THIRD distinct failing action, because the remedy is a different half of
            # the seam: the dispatch is not "not happening", it is unreachable — Step 0.5
            # degrades before it gets there. Telling this user to check their dispatch
            # would point at the wrong place, which is how a signal stops being read.
            _dl_evidence = (
                "every recent wrapup brief degraded — Step 0.5 never reaches the dispatch"
            )
            _dl_action = (
                "Run `python -m harness_maker.wrapup_brief --root . --slug <slug>` from the "
                "BASE repo and read verdict.reason — the brief is not derivable, so the "
                "delegated body is being skipped before any dispatch is attempted"
            )
        elif _dl_verdict == "no-dispatch":
            _dl_evidence = (
                "wrapup derived its brief but dispatched no subagent in the recent window"
            )
            _dl_action = (
                "Step 0.5 of /hm:wrapup is deriving the brief and then not dispatching "
                "stage-delegate — check that the brief reports status: ok and that the "
                "dispatch is actually issued"
            )
        elif _dl_verdict == "unavailable-only":
            _dl_evidence = "wrapup self-skips dispatch — this IDE has no subagent tool (N-A)"
            _dl_action = None
        else:
            _dl_evidence = "wrapup delegation dispatched in the recent window"
            _dl_action = None
    signals.append(_signal("delegation_fires", _dl_passed, 0, _dl_evidence, _dl_action))

    # Render-drift guard (PLAN-wrapup-waiver-enforcement ADR-004/C5): the
    # task-driven oracle-waiver advisory (wrapup Step 3.6) is baked at render time
    # on the dev_mode branch. If harness.yaml's dev_mode was flipped without
    # re-rendering, the rendered wrapup either silently LACKS the advisory
    # (task-driven) or mis-fires it (spec-driven). N-A (no signal) when the wrapup
    # command or a recognizable dev_mode is absent.
    wrapup_cmd = claude / "commands" / "hm" / "wrapup.md"
    _dev_mode: str | None = None
    _hy_path = claude / "harness.yaml"
    if _hy_path.is_file():
        try:
            from harness_maker.io_utils import load_harness_yaml as _lhy

            _hy2 = _lhy(_hy_path)
            _dm = _hy2.get("dev_mode") if isinstance(_hy2, dict) else None
            _dev_mode = _dm if isinstance(_dm, str) else None
        except Exception:  # noqa: BLE001 — degrade to N-A, never crash readiness
            _dev_mode = None
    _has_advisory: bool | None = None
    if wrapup_cmd.is_file() and _dev_mode in ("task-driven", "spec-driven"):
        try:
            _has_advisory = "waiver-check" in wrapup_cmd.read_text(encoding="utf-8")
        except (OSError, ValueError):
            _has_advisory = None  # unreadable render → N-A, never crash /hm:health
    if _has_advisory is not None and _dev_mode in ("task-driven", "spec-driven"):
        _matched = _has_advisory == (_dev_mode == "task-driven")
        signals.append(
            _signal(
                "wrapup_oracle_waiver_dev_mode_match",
                _matched,
                15,
                "rendered wrapup oracle-waiver advisory matches harness.yaml dev_mode"
                if _matched
                else f"rendered wrapup advisory MISMATCHES dev_mode={_dev_mode} "
                f"(advisory {'present' if _has_advisory else 'absent'}) — stale render",
                None
                if _matched
                else "Re-render with /harness-maker:make --update so wrapup Step 3.6 "
                "matches the current dev_mode (oracle-waiver advisory render-drift)",
            )
        )

    # Render-drift guard (PLAN-spec-optional-task-driven ADR-003): plan Step 1.7
    # and verify Check 6 are render-gated on dev_mode == spec-driven. spec_need's
    # runtime guard backstops verify at execution time, but plan-side enforcement
    # is LLM-prose (unreachable at runtime), so a stale render (dev_mode flipped
    # without re-render) is surfaced HERE. Mirrors wrapup_oracle_waiver_dev_mode_match.
    # Marker = the spec-driven-only `spec_need` CLI calls both stages render.
    # N-A when either command file is absent/unreadable or dev_mode is unrecognized.
    plan_cmd = claude / "commands" / "hm" / "plan.md"
    verify_cmd = claude / "commands" / "hm" / "verify.md"
    if _dev_mode in ("task-driven", "spec-driven") and plan_cmd.is_file() and verify_cmd.is_file():
        try:
            _plan_gated = "spec_need" in plan_cmd.read_text(encoding="utf-8")
            _verify_gated = "spec_need" in verify_cmd.read_text(encoding="utf-8")
        except (OSError, ValueError):
            pass  # unreadable render → N-A, never crash /hm:health
        else:
            _is_spec = _dev_mode == "spec-driven"
            _pv_matched = (_plan_gated == _is_spec) and (_verify_gated == _is_spec)
            signals.append(
                _signal(
                    "plan_verify_dev_mode_match",
                    _pv_matched,
                    15,
                    "rendered plan Step 1.7 + verify Check 6 match harness.yaml dev_mode"
                    if _pv_matched
                    else f"rendered plan/verify spec-need gating MISMATCHES dev_mode={_dev_mode} "
                    f"(plan Step 1.7 {'present' if _plan_gated else 'absent'}, "
                    f"verify Check 6 {'present' if _verify_gated else 'absent'}) — stale render",
                    None
                    if _pv_matched
                    else "Re-render with /harness-maker:make --update so plan Step 1.7 + "
                    "verify Check 6 match the current dev_mode (spec-need render-drift)",
                )
            )

    # Advisory — stale judgment-AC verdicts (PLAN-judgment-stale-health-display).
    # weight=0 AND hard_gate=False so it surfaces in /hm:health WITHOUT docking the
    # structural score: the find-unjudged Production gate is the teeth (ADR-001).
    # N-A (no signal) when there is no judgment AC to talk about; fail-LOUD (a failed
    # signal, NOT N-A) on a malformed machine SPEC — present-but-unreadable means
    # freshness is UNKNOWN, unlike the waiver advisory's genuinely-absent render
    # (ADR-002). Subject-hash errors come back from the detector as stale ids (not
    # exceptions), so the only exception escaping it is a load()/parse failure.
    specs_dir = project_dir / "specs"
    if specs_dir.is_dir():
        from harness_maker.spec_machine import _judgment_in_scope
        from harness_maker.spec_machine import load as _load_machine
        from harness_maker.spec_machine import select_judgment as _select_judgment
        from harness_maker.spec_machine import stale_judgment_verdicts as _stale_verdicts

        stale_ids: list[str] = []
        unreadable_specs: list[str] = []
        judgment_ac_total = 0
        fresh_pass_total = 0
        specs_with_judgment = 0
        for yp in sorted(specs_dir.glob("SPEC-*.machine.yaml")):
            spec_id = yp.name.removesuffix(".machine.yaml")
            # Narrow catch (REVIEW F2, R1+Codex consensus): only a load/parse failure
            # marks a SPEC malformed. A genuine internal bug (AttributeError/TypeError)
            # must propagate LOUD, not be mislabeled as the user's "malformed SPEC".
            try:
                judgment_acs = _select_judgment(_load_machine(yp))
                spec_stale = _stale_verdicts(yp, project_dir)
            except (OSError, yaml.YAMLError, ValidationError, ValueError):
                unreadable_specs.append(spec_id)
                continue
            if judgment_acs:
                specs_with_judgment += 1
                judgment_ac_total += len(judgment_acs)
            # Count only IN-SCOPE passes (REVIEW F1, R1+R2 consensus): a pass whose
            # subject is fully absent on disk is out-of-scope (the detector skips it),
            # so it is neither fresh nor stale — it must not inflate the "N fresh" tally.
            fresh_pass_total += sum(
                1
                for a in judgment_acs
                if a.judgment_verdict == "pass" and _judgment_in_scope(a, project_dir)
            )
            stale_ids.extend(f"{spec_id}:{ac_id}" for ac_id in spec_stale)

        if judgment_ac_total > 0 or unreadable_specs:
            frags: list[str] = []
            actions: list[str] = []
            if stale_ids:
                frags.append("stale judgment verdict(s): " + ", ".join(stale_ids))
                actions.append(
                    "Re-run /hm:wrapup (the find-unjudged gate blocks until the "
                    "judgment-reviewer re-issues a pass for the drifted subject)"
                )
            if unreadable_specs:
                frags.append(
                    "could not verify freshness — malformed machine SPEC(s): "
                    + ", ".join(unreadable_specs)
                )
                actions.append(
                    "Run python -m harness_maker.spec_machine validate on the named SPEC(s)"
                )
            judgment_passed = not stale_ids and not unreadable_specs
            signals.append(
                _signal(
                    "judgment_verdict_freshness",
                    judgment_passed,
                    0,  # ADR-001: advisory display-only — never docks the structural score
                    f"{fresh_pass_total} judgment verdict(s) fresh across "
                    f"{specs_with_judgment} SPEC(s)"
                    if judgment_passed
                    else " ; ".join(frags),
                    None if judgment_passed else "; ".join(actions),
                    hard_gate=False,  # ADR-001: pinned, not defaulted — never a stealth gate
                )
            )

    # Advisory — spec-need forcing/waiver rate (PLAN-spec-requirement-gate ADR-008).
    # weight=0 AND hard_gate=False — display-only visibility into over/under-forcing;
    # never docks the structural score (mirrors judgment_verdict_freshness ADR-001).
    # N-A (no signal) when there is no spec-need-*.jsonl ledger at all (absent-case
    # per CLAUDE.md §absent-case rule — no false finding, no crash; degrade on
    # malformed lines).
    #
    # FIX 4 (R1-P1a): verdict scan reads ONLY verdict ledgers spec-need-{target}.jsonl,
    # EXCLUDING spec-need-waiver-*.jsonl (whose "verdict" field duplicates the original
    # verdict, inflating the forcing count).
    # FIX 5 (R1-P1b): waiver count is derived from the count of waiver receipt files
    # spec-need-waiver-*.jsonl — "verdict=='waived'" was never produced by any code path.
    _obs_dir = claude / "observability"
    # Verdict ledgers only — skip waiver receipts (FIX 4).
    _sn_verdict_files = (
        [f for f in sorted(_obs_dir.glob("spec-need-*.jsonl")) if "-waiver-" not in f.name]
        if _obs_dir.is_dir()
        else []
    )
    # Waiver receipt files — counted directly (FIX 5).
    _sn_waiver_files = (
        sorted(_obs_dir.glob("spec-need-waiver-*.jsonl")) if _obs_dir.is_dir() else []
    )
    if _sn_verdict_files:
        _sn_verdict_counts: dict[str, int] = {}
        _sn_total = 0
        for _sn_fp in _sn_verdict_files:
            try:
                for _sn_line in _sn_fp.read_text(encoding="utf-8").splitlines():
                    _sn_line = _sn_line.strip()
                    if not _sn_line:
                        continue
                    try:
                        _sn_ev = json.loads(_sn_line)
                    except json.JSONDecodeError:
                        continue  # degrade on malformed line, never crash
                    _sn_v = (
                        _sn_ev.get("verdict", "not-evaluated")
                        if isinstance(_sn_ev, dict)
                        else "not-evaluated"
                    )
                    _sn_verdict_counts[_sn_v] = _sn_verdict_counts.get(_sn_v, 0) + 1
                    _sn_total += 1
            except OSError:
                continue  # unreadable file → degrade, never crash
        if _sn_total > 0:
            _sn_forcing = sum(
                _sn_verdict_counts.get(v, 0) for v in ("add", "change", "delete", "not-evaluated")
            )
            _sn_none = _sn_verdict_counts.get("none", 0)
            # Count waiver receipts from the dedicated waiver files (FIX 5).
            _sn_waived = len(_sn_waiver_files)
            _sn_waiver_rate = (
                f"{_sn_waived}/{_sn_forcing} waived" if _sn_forcing > 0 else "0 forcing verdicts"
            )
            _sn_count_parts_list = [
                f"{v}={_sn_verdict_counts[v]}"
                for v in ("add", "change", "delete", "none", "not-evaluated")
                if _sn_verdict_counts.get(v, 0) > 0
            ]
            if _sn_waived > 0:
                _sn_count_parts_list.append(f"waived={_sn_waived}")
            _sn_count_parts = ", ".join(_sn_count_parts_list)
            _sn_evidence = (
                f"spec-need ledger: {_sn_total} event(s) — {_sn_count_parts}; "
                f"forcing={_sn_forcing}, none={_sn_none}, {_sn_waiver_rate}"
            )
            signals.append(
                _signal(
                    "spec_need_forcing",
                    True,  # advisory: always passing — the content is the information
                    0,  # ADR-008: display-only, never docks the structural score
                    _sn_evidence,
                    None,
                    hard_gate=False,  # ADR-008: pinned, not defaulted — never a stealth gate
                )
            )

    settings_path = claude / "settings.json"
    settings = _read_json_with_optional_frontmatter(settings_path)
    perms = settings.get("permissions") if isinstance(settings, dict) else None
    deny = perms.get("deny") if isinstance(perms, dict) else None
    deny_list: list[str] = deny if isinstance(deny, list) else []

    # The main-session deny-list is opt-in (PermissionsConfig.deny_dangerous,
    # default off — solo-friendly). A deliberately-empty deny is a config choice,
    # not a missing guardrail, so both deny signals PASS on the strength of the
    # setting when the user opted out (no penalty); they enforce a non-empty /
    # covering deny only when deny_dangerous=true.
    deny_opt_in = False
    targets_cfg: list[str] = []
    harness_yaml = claude / "harness.yaml"
    if harness_yaml.is_file():
        try:
            from harness_maker.io_utils import load_harness_yaml

            _hy = load_harness_yaml(harness_yaml)
            _hy_perms = _hy.get("permissions") if isinstance(_hy, dict) else None
            deny_opt_in = bool(
                isinstance(_hy_perms, dict) and _hy_perms.get("deny_dangerous", False)
            )
            _t = _hy.get("targets") if isinstance(_hy, dict) else None
            targets_cfg = [str(x) for x in _t] if isinstance(_t, list) else []
        except Exception:
            deny_opt_in = False
            targets_cfg = []

    # Live runtime probe (ADR-004 of PLAN-multisession-10-fleet-hardening): the
    # static `sessionid_envfile_registered` signal proves only that the hook is in
    # hooks.json, NOT that HM_SESSION_ID actually reached the environment at runtime
    # (env-file plumbing can fail on WSL2; Cursor/Codex never set it). This probes
    # the health command's OWN session. HARD-GATE on Claude Code so a degraded loop
    # substrate drops the dimension below green instead of being masked by the >100
    # additive weight; N-A for Cursor/Codex-only harnesses (the var is structurally
    # absent there). An old harness with no `targets` defaults to claude-code.
    #
    # CRITICAL: only emit when we are actually inside a Claude Code session, keyed
    # on `CLAUDECODE` — verified (REVIEW follow-up env probe) to be the session
    # marker Claude Code DOES export to slash-command Bash subprocesses. Outside a
    # session (unit tests, CI, `make` audit, Cursor/Codex) CLAUDECODE is unset → N-A,
    # so the hard-gate never floors a static disk-scan context.
    #
    # The VALUE cannot come from `os.environ` (ADR-001). `sessionid_envfile` writes
    # `HM_SESSION_ID=<v>` into `$CLAUDE_ENV_FILE`, which Claude Code sources into the
    # Bash-tool shell as an UNEXPORTED shell variable: `echo "$HM_SESSION_ID"` works,
    # `os.environ.get("HM_SESSION_ID")` is None in every subprocess. Reading the env
    # here therefore failed unconditionally and hard-gated this dimension to 0 in every
    # real session. The slash command passes the value in instead; the env read survives
    # only as a fallback for a host that does export it.
    claude_target = (not targets_cfg) or "claude-code" in targets_cfg
    in_session = bool(os.environ.get("CLAUDECODE"))
    if claude_target and in_session:
        resolved = session_id if session_id is not None else os.environ.get("HM_SESSION_ID")
        if resolved is None:
            # The caller never wired the probe — a render predating `--session-id`.
            # Weight 0 is the honest value, not a hedge: this dimension's signal weights
            # sum to 145 against a cap of 100, so ANY failure of weight <= 45 moves the
            # score by exactly zero. Declaring 15 would read as a cost that provably is
            # not charged. The `action` is load-bearing — `improvement.py` drops signals
            # with `action is None` before priority is computed, and that is the only
            # channel carrying the remedy (ADR-004).
            signals.append(
                _signal(
                    "sessionid_envfile_probe_wired",
                    False,
                    0,
                    "the live session-id probe was not wired: this command did not pass "
                    "--session-id, so whether the SessionStart plumbing works is unknown "
                    "(a stale render, not a degraded session)",
                    "Re-render the harness with /harness-maker:make --update so "
                    '/hm:health passes --session-id "$HM_SESSION_ID"',
                )
            )
        else:
            live_ok = bool(resolved)
            signals.append(
                _signal(
                    "sessionid_envfile_live",
                    live_ok,
                    0,  # hard-gate, not additive — gating is via hard_gate, not weight
                    "HM_SESSION_ID is set (SessionStart env-file plumbing live)"
                    if live_ok
                    else "HM_SESSION_ID unset at runtime — SessionStart env-file plumbing "
                    "is not firing; a /hm:loop here self-stops after one iteration (the "
                    "Stop-hook has your session_id from stdin but the marker header is "
                    "empty, so content-match fails and the loop is allowed to stop) "
                    "while the static hooks.json check may still read green",
                    None
                    if live_ok
                    else "Ensure the SessionStart sessionid_envfile hook fires and "
                    "CLAUDE_ENV_FILE is honored; re-render with /hm:make --update and "
                    "restart the session",
                    hard_gate=True,
                )
            )

    deny_present_ok = (not deny_opt_in) or len(deny_list) > 0
    signals.append(
        _signal(
            "permissions_deny_present",
            deny_present_ok,
            20,
            f"settings.json permissions.deny has {len(deny_list)} pattern(s)"
            if deny_list
            else (
                "permissions.deny intentionally empty (harness.yaml "
                "permissions.deny_dangerous=false — solo opt-out)"
                if not deny_opt_in
                else "settings.json permissions.deny is empty or missing"
            ),
            None
            if deny_present_ok
            else "Add settings.json `permissions.deny` blocking dangerous Bash patterns",
        )
    )

    deny_text = " ".join(str(p) for p in deny_list).lower()
    matched = [p for p in _DANGEROUS_DENY_PATTERNS if p.lower() in deny_text]
    cov_ok = (not deny_opt_in) or len(matched) >= _DENY_COVERAGE_MIN
    cov_evidence = (
        f"Deny patterns cover {len(matched)}/{len(_DANGEROUS_DENY_PATTERNS)} dangerous patterns"
        if matched
        else (
            "deny opted out (harness.yaml permissions.deny_dangerous=false) — not a finding"
            if not deny_opt_in
            else "Deny list does not cover dangerous patterns"
        )
    )
    signals.append(
        _signal(
            "deny_covers_dangerous",
            cov_ok,
            15,
            cov_evidence,
            None if cov_ok else "Block rm -rf, curl|sh, writes to /etc and ~/.ssh",
        )
    )

    sec_dir = claude / "observability" / "security"
    high_count = 0
    if sec_dir.is_dir():
        for f in sec_dir.glob("findings-*.jsonl"):
            try:
                for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                    # Why both "high" and "P0": the 7 gates use two severity
                    # vocabularies — most emit "high", but hallucination and
                    # prod_name_guard emit "P0" (cli.py gates on {"high","P0"}).
                    # Counting only "high" left critical P0 findings invisible.
                    if (
                        '"severity": "high"' in line
                        or '"severity":"high"' in line
                        or '"severity": "P0"' in line
                        or '"severity":"P0"' in line
                    ):
                        high_count += 1
            except OSError:
                continue
    sec_action = (
        None
        if high_count == 0
        else (
            f"Resolve {high_count} high/P0-severity finding(s) under "
            ".claude/observability/security/"
        )
    )
    signals.append(
        _signal(
            "no_high_security_findings",
            high_count == 0,
            15,
            f"{high_count} high/P0-severity security finding(s) recorded"
            if high_count
            else "No high/P0-severity security findings (or not yet scanned)",
            sec_action,
        )
    )

    return DimensionScore(name="guardrails", score=_score_signals(signals), signals=signals)


def _dim_verification(project_dir: Path) -> DimensionScore:
    """Tests for detected stack + CI + verify-before-completion.

    ADR-004: unknown-stack (`stacks == set()`) auto-degrade — stack_detected
    and tests_present signals run at reduced weight (5/10 vs 20/30) so
    non-standard projects (board-yaml, shell-only) don't get P0-flagged.
    """
    signals: list[Signal] = []
    stacks = _detect_stacks(project_dir)
    stacks_unknown = not stacks

    # Stack detection — degrade weight when unknown.
    signals.append(
        _signal(
            "stack_detected",
            bool(stacks),
            5 if stacks_unknown else 20,
            f"Detected stacks: {', '.join(sorted(stacks))}"
            if stacks
            else "No language stack detected (non-standard project)",
            None
            if stacks
            else "If non-standard project, this is expected. Otherwise add pyproject.toml/etc.",
        )
    )

    has_tests = bool(stacks) and any(
        _STACK_TESTERS[s](project_dir) for s in stacks if s in _STACK_TESTERS
    )
    signals.append(
        _signal(
            "tests_present",
            has_tests,
            10 if stacks_unknown else 30,
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

    # PLAN-locale-and-command-observability ADR-002/005: presence-audit that the
    # locale directive + start/end summary banners landed in the rendered stage +
    # fused-workflow commands (the wrappers that carry them). Meta commands
    # (make/help/loop/loop-p5-batch/…) use their own templates and rely on the
    # persistent CLAUDE.md/AGENTS.md anchor instead, so they MUST be excluded — note
    # loop-p5-batch has a hyphen, so the `fused` classifier (`"-" in stem`) sweeps it
    # in; without the meta denylist both signals false-fail on every install. REVIEW P1.
    meta_cmds = {"make", "help", "health", "configure", "uninstall", "loop", "loop-p5-batch"}
    stage_fused = [
        c for c in commands if (c.stem in atomic_stages or c in fused) and c.stem not in meta_cmds
    ]
    _bodies = {c: _read_text(c) for c in stage_fused}
    loc_hits = sum(1 for t in _bodies.values() if "<!-- @hm:output_language -->" in t)
    loc_ok = (not stage_fused) or loc_hits == len(stage_fused)
    signals.append(
        _signal(
            "output_language_present",
            loc_ok,
            15,
            f"{loc_hits}/{len(stage_fused)} stage/fused commands carry the locale directive"
            if stage_fused
            else "No stage/fused commands to check",
            None
            if loc_ok
            else "Re-render via /hm:make — commands missing the locale directive "
            "(the output_language partial silently dropped from a wrapper)",
        )
    )
    ban_markers = ("<!-- @hm:banner:start -->", "<!-- @hm:banner:end -->")
    ban_hits = sum(1 for t in _bodies.values() if all(m in t for m in ban_markers))
    ban_ok = (not stage_fused) or ban_hits == len(stage_fused)
    signals.append(
        _signal(
            "start_end_summary_present",
            ban_ok,
            15,
            f"{ban_hits}/{len(stage_fused)} stage/fused commands carry start + end summary banners"
            if stage_fused
            else "No stage/fused commands to check",
            None
            if ban_ok
            else "Re-render via /hm:make — commands missing a start or end summary banner "
            "(step_manifest or stage_end_summary partial silently dropped)",
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
        has_real_lessons = len(non_empty_lines) > 5 or any(
            line.startswith("## ") for line in non_empty_lines
        )
    signals.append(
        _signal(
            "failures_md_has_content",
            has_real_lessons,
            30,
            "failures.md contains accumulated lessons"
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
    """observability dir + telemetry files (legacy + date-sharded) + dashboard.md.

    Telemetry rotates per-day to `metrics-YYYY-MM-DD.jsonl` (see ADR-103 in
    `_metrics_io.py`); both presence and sample-count signals count across
    the full rotation set plus the legacy `metrics.jsonl` fallback.
    """
    signals: list[Signal] = []
    obs = project_dir / ".claude" / "observability"
    dashboard = obs / "dashboard.md"
    metrics_files = _candidate_files(obs, days=365) if obs.is_dir() else []

    signals.append(
        _signal(
            "observability_dir_present",
            obs.is_dir(),
            25,
            ".claude/observability/ exists" if obs.is_dir() else ".claude/observability/ missing",
            None if obs.is_dir() else "Run /hm:make to scaffold the observability directory",
        )
    )
    has_telemetry = bool(metrics_files)
    signals.append(
        _signal(
            "metrics_jsonl_present",
            has_telemetry,
            25,
            f"telemetry present ({len(metrics_files)} file(s))"
            if has_telemetry
            else "no telemetry files (metrics.jsonl or metrics-YYYY-MM-DD.jsonl)",
            None
            if has_telemetry
            else (
                "First Claude Code tool use will create this file (PostToolUse hook is installed)."
            ),
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
    for path in metrics_files:
        try:
            sample_size += sum(1 for line in _read_text(path).splitlines() if line.strip())
        except OSError:
            continue
    has_samples = sample_size >= 5
    signals.append(
        _signal(
            "metrics_has_samples",
            has_samples,
            25,
            f"telemetry has {sample_size} entr{'y' if sample_size == 1 else 'ies'} "
            f"across {len(metrics_files)} file(s)"
            if has_telemetry
            else "no telemetry files",
            None if has_samples else "Use Claude Code for ≥ 5 turns to accumulate telemetry",
        )
    )

    return DimensionScore(
        name="observability_setup", score=_score_signals(signals), signals=signals
    )


def _dim_model_routing(project_dir: Path) -> DimensionScore:
    """ADR-010 (PLAN-model-routing-multi-ide): 3 advisory sub-checks per IDE target.

    All checks are advisory (score-only, not failure-grade):
    (a) Claude target + any agent_models.<*>.claude set → relies on Anthropic
        issue #43869 which is currently silently broken — subagents inherit
        parent model regardless. Render frontmatter anyway for forward-compat.
    (b) Cursor target + any agent_models.<*>.cursor value matching a known
        alias key (PRE-resolution) → user opted into alias-form; renderer
        normalizes via CURSOR_MODEL_IDS, but the raw value in harness.yaml
        may surprise future readers and pre-3.3 Cursor versions need
        concrete IDs.
    (c) Codex target + agents with reasoning_effort=None → the dominant cost
        lever isn't pinned; defaults will apply.
    """
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.presets import CURSOR_MODEL_IDS

    signals: list[Signal] = []
    harness_yaml = project_dir / ".claude" / "harness.yaml"
    if not harness_yaml.exists():
        signals.append(
            _signal(
                "harness_yaml_present",
                False,
                100,
                ".claude/harness.yaml missing — cannot evaluate model routing",
                "Run /hm:make to scaffold the harness",
            )
        )
        return DimensionScore(name="model_routing", score=_score_signals(signals), signals=signals)

    try:
        import yaml as _yaml

        data = load_harness_yaml(harness_yaml)
    except (OSError, _yaml.YAMLError, ValueError, KeyError):
        # Best-effort readiness: malformed/inaccessible harness.yaml → empty
        # data, advisory checks still surface as N/A. AssertionError from a
        # logic bug intentionally NOT caught — surface it for fixing (review
        # security-reviewer P2 fix).
        data = {}
    targets = data.get("targets") or []
    targets_set = {str(t) for t in targets} if isinstance(targets, list) else set()
    raw_agent_models = data.get("agent_models") or {}
    if not isinstance(raw_agent_models, dict):
        raw_agent_models = {}

    # (a) Claude — #43869 advisory
    has_claude = "claude-code" in targets_set
    claude_overrides = [
        name
        for name, spec in raw_agent_models.items()
        if isinstance(spec, dict) and spec.get("claude")
    ]
    if has_claude:
        claude_ok = not claude_overrides  # no override → no reliance on #43869
        signals.append(
            _signal(
                "claude_subagent_routing_43869",
                claude_ok,
                33,
                "no per-agent claude overrides"
                if claude_ok
                else (
                    f"{len(claude_overrides)} agent(s) with `claude:` "
                    f"override — Anthropic #43869 silently ignores subagent "
                    f"model frontmatter today (frontmatter rendered for "
                    f"forward-compat). See docs/HOW-IT-WORKS.md > Agent Models."
                ),
                None
                if claude_ok
                else (
                    "Track https://github.com/anthropics/claude-code/issues/43869; "
                    "overrides will activate when fix lands."
                ),
            )
        )
    else:
        # No claude target → check inapplicable, pass for free
        signals.append(
            _signal(
                "claude_subagent_routing_43869",
                True,
                33,
                "claude-code not in targets — check N/A",
                None,
            )
        )

    # (b) Cursor — alias vs concrete-ID advisory (inspects PRE-resolution raw values)
    has_cursor = "cursor" in targets_set
    cursor_alias_overrides = [
        name
        for name, spec in raw_agent_models.items()
        if isinstance(spec, dict)
        and isinstance(spec.get("cursor"), str)
        and spec["cursor"] in CURSOR_MODEL_IDS
    ]
    if has_cursor:
        cursor_ok = not cursor_alias_overrides
        signals.append(
            _signal(
                "cursor_alias_vs_concrete_id",
                cursor_ok,
                33,
                "no alias-form cursor values in agent_models"
                if cursor_ok
                else (
                    f"{len(cursor_alias_overrides)} agent(s) wrote alias-form "
                    f"`cursor:` (renderer normalizes via CURSOR_MODEL_IDS; "
                    f"works on Cursor 3.3+; on 2.4-3.2 the renderer emits "
                    f"concrete IDs so this is informational only)."
                ),
                None,
            )
        )
    else:
        signals.append(
            _signal(
                "cursor_alias_vs_concrete_id",
                True,
                33,
                "cursor not in targets — check N/A",
                None,
            )
        )

    # (c) Codex — reasoning_effort coverage
    has_codex = "codex" in targets_set
    codex_missing_effort = [
        name
        for name, spec in raw_agent_models.items()
        if isinstance(spec, dict)
        and (
            not isinstance(spec.get("codex"), dict)
            or not spec.get("codex", {}).get("reasoning_effort")
        )
    ]
    if has_codex:
        # Codex check passes when the override map either is empty (preset map
        # applies) or every override sets reasoning_effort. Missing effort on a
        # user override means the default profile applies — advisory only.
        codex_ok = not raw_agent_models or not codex_missing_effort
        signals.append(
            _signal(
                "codex_reasoning_effort_coverage",
                codex_ok,
                34,
                "all per-agent codex overrides set reasoning_effort, or no overrides"
                if codex_ok
                else (
                    f"{len(codex_missing_effort)} agent(s) override claude/cursor "
                    f"but not codex.reasoning_effort — Codex default profile applies. "
                    f"See `codex -p cheap` / `codex -p deep` (installed by "
                    f"`harness-maker make` into ~/.codex/config.toml) "
                    f"for invocation-time cost control."
                ),
                None,
            )
        )
    else:
        signals.append(
            _signal(
                "codex_reasoning_effort_coverage",
                True,
                34,
                "codex not in targets — check N/A",
                None,
            )
        )

    return DimensionScore(name="model_routing", score=_score_signals(signals), signals=signals)


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
    """Count .md files in .claude/ without harness-maker provenance frontmatter.

    Sniff window for ``content_hash:`` is 2000 bytes — large enough to cover
    agent frontmatter blocks that include both ``permissions: allow`` and
    ``permissions: deny`` lists (longest observed today is executor.md with
    content_hash at byte 809). 500-byte windows mis-counted any agent with
    a deny baseline as a "user file", inflating ceremony_penalty (0.26.0
    quality-gate regression — PLAN-codex-second-llm-integration pushed two
    more agents over the old 500-byte boundary).
    """
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
        if not (text.startswith("---\n") and "content_hash:" in text[:2000]):
            count += 1
    return count


# ── public API ──────────────────────────────────────────────────────────────


def compute_readiness(
    project_dir: Path, preset: Preset, *, session_id: str | None = None
) -> ReadinessResult:
    """Compute Layer-1 readiness across 7 deterministic dimensions.

    Layer 3 (cache_efficiency) and Layer 2 (LLM-judged content quality) are
    folded in by the orchestrator at /hm:ai-readiness, not here.

    ``session_id`` is forwarded verbatim to ``_dim_guardrails`` — see its tri-state
    contract. Keyword-only and optional, so existing callers land in the ``None``
    branch rather than silently claiming a healthy probe.
    """
    weights = WEIGHTS_SIDE if preset == Preset.SIDE else WEIGHTS_PROD

    dims: dict[str, DimensionScore] = {
        "context_quality": _dim_context_quality(project_dir, preset),
        "guardrails": _dim_guardrails(project_dir, session_id=session_id),
        "verification": _dim_verification(project_dir),
        "workflow_clarity": _dim_workflow_clarity(project_dir),
        "memory_continuity": _dim_memory_continuity(project_dir),
        "observability_setup": _dim_observability_setup(project_dir),
        "governance": _dim_governance(project_dir, preset),
        "model_routing": _dim_model_routing(project_dir),
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
