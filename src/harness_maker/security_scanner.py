"""Security scanner orchestrator — invokes gates and persists findings.

Gates (7 total):
1. secrets — hardcoded credentials / API keys
2. permissions — overly permissive settings.json
3. hook_injection — shell=True / eval patterns in hooks
4. dependency_cves — known CVEs in dependencies
5. prompt_injection — hidden prompt patterns in markdown
6. hallucination — AST-detected imports of non-existent packages (Phase 2)
7. prod_name_guard — production environment name/sequence detection (Phase 8)

Returns aggregated findings; persists to ``.claude/observability/security/findings-<date>.jsonl``.
"""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker._metrics_io import iter_recent_entries
from harness_maker.llm_judge import AnthropicJudgeClient, JudgeClient
from harness_maker.models import Finding
from harness_maker.secscan import (
    scan_dependency_cves,
    scan_hook_injection,
    scan_permissions,
    scan_prompt_injection_llm,
    scan_secrets,
)
from harness_maker.secscan.hallucination import scan_directory as scan_hallucination
from harness_maker.secscan.prod_name_guard import scan_sequence as scan_prod_sequence


def _load_recent_tool_calls(target_dir: Path, window: int = 50) -> list[dict[str, Any]]:
    """Read the last ``window`` post_tool_use entries with ``tool_input``.

    Delegates I/O to :func:`harness_maker._metrics_io.iter_recent_entries`,
    so date-sharded ``metrics-YYYY-MM-DD.jsonl`` files plus the legacy
    ``metrics.jsonl`` are unified (ADR-103, 0.7.1). Each emitted call has
    ``tool_name`` + ``args`` (decoded from the truncated ``tool_input``
    field that telemetry persists since 0.7.0); pre-0.7.0 entries lack
    ``tool_input`` and are silently skipped.
    """
    obs_dir = target_dir / ".claude" / "observability"
    calls: list[dict[str, Any]] = []
    for parsed in iter_recent_entries(obs_dir, days=window, event="post_tool_use"):
        tool_name = parsed.get("tool_name")
        raw_input = parsed.get("tool_input")
        if not isinstance(tool_name, str) or not isinstance(raw_input, str):
            continue
        try:
            args = json.loads(raw_input)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(args, dict):
            continue
        calls.append({"tool_name": tool_name, "args": args})
        if len(calls) >= window:
            break
    calls.reverse()
    return calls


def _persist(findings: list[Finding], target_dir: Path) -> Path:
    out_dir = target_dir / ".claude" / "observability" / "security"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out_path = out_dir / f"findings-{today}.jsonl"
    with out_path.open("a", encoding="utf-8") as fp:
        for f in findings:
            fp.write(json.dumps(f.model_dump(), ensure_ascii=False) + "\n")
    return out_path


def _on_finding_policy(harness_config: dict[str, Any] | None) -> str:
    if not harness_config:
        return "warn"
    sec = harness_config.get("security")
    if not isinstance(sec, dict):
        return "warn"
    on_finding = sec.get("on_finding")
    if not isinstance(on_finding, dict):
        return "warn"
    high = on_finding.get("high")
    if isinstance(high, str) and high in {"warn", "block", "allow"}:
        return high
    return "warn"


def _build_pi_client() -> JudgeClient | None:
    """Best-effort Anthropic client for the prompt-injection LLM second pass."""
    try:
        return AnthropicJudgeClient()
    except Exception:  # noqa: BLE001 — falling back to regex-only is fine
        return None


_SCAN_TTL = 86400.0  # 24 hours


def _config_mtimes(target_dir: Path) -> float:
    """Max mtime of security-relevant config files."""
    candidates = [
        target_dir / "uv.lock",
        target_dir / "pyproject.toml",
    ]
    claude_dir = target_dir / ".claude"
    if claude_dir.is_dir():
        candidates.extend(claude_dir.rglob("*"))
    max_mt = 0.0
    for p in candidates:
        with contextlib.suppress(OSError):
            max_mt = max(max_mt, p.stat().st_mtime)
    return max_mt


def _check_fresh_scan(target_dir: Path) -> list[Finding] | None:
    """Return cached findings if scan is fresh (< 24h, no config changes)."""
    sec_dir = target_dir / ".claude" / "observability" / "security"
    if not sec_dir.is_dir():
        return None

    findings_files = sorted(sec_dir.glob("findings-*.jsonl"), reverse=True)
    if not findings_files:
        return None

    latest = findings_files[0]
    try:
        scan_mtime = latest.stat().st_mtime
    except OSError:
        return None

    import time

    if time.time() - scan_mtime > _SCAN_TTL:
        return None

    config_mt = _config_mtimes(target_dir)
    if config_mt > scan_mtime:
        return None

    try:
        lines = latest.read_text(encoding="utf-8").strip().splitlines()
        return [Finding(**json.loads(line)) for line in lines if line.strip()]
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def scan_all(
    target_dir: Path,
    harness_config: dict[str, Any] | None = None,
    *,
    pi_client: JudgeClient | None = None,
    force: bool = False,
) -> list[Finding]:
    """Run all 7 security gates against ``target_dir``; persist + return findings.

    The prompt-injection gate runs both regex and an LLM second pass (via
    ``scan_prompt_injection_llm``). On any LLM transport error the gate
    silently falls back to regex-only — the security scanner must never
    raise, since blocking edits on a flaky network call is worse than a
    one-off missed polymorphic injection.
    """
    if not force:
        cached = _check_fresh_scan(target_dir)
        if cached is not None:
            return cached

    findings: list[Finding] = []

    findings.extend(scan_secrets(target_dir))

    settings = target_dir / ".claude" / "settings.json"
    if not settings.exists():
        settings = target_dir / "settings.json"
    findings.extend(scan_permissions(settings))

    hooks = target_dir / ".claude" / "hooks" / "hooks.json"
    if not hooks.exists():
        hooks = target_dir / "hooks" / "hooks.json"
    findings.extend(scan_hook_injection(hooks))

    findings.extend(scan_dependency_cves(target_dir))

    # Gate 6: Hallucination — AST-detected non-existent imports
    findings.extend(scan_hallucination(target_dir))

    # Gate 7: Production-name guard — sequence detection over recent tool history.
    # No-op when metrics.jsonl is empty or all entries pre-date 0.7.0
    # tool_input persistence (graceful upgrade).
    tool_calls = _load_recent_tool_calls(target_dir)
    findings.extend(scan_prod_sequence(tool_calls))

    # Prompt-injection scan: walk markdown files for hidden patterns + LLM.
    if pi_client is None:
        pi_client = _build_pi_client()
    pi_text_sources: list[Path] = []
    for ext in ("*.md", "*.txt"):
        pi_text_sources.extend(target_dir.rglob(ext))
    for src in pi_text_sources:
        if any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in src.parts):
            continue
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        per_file = (
            scan_prompt_injection_llm(text, client=pi_client)
            if pi_client is not None
            else scan_prompt_injection_regex_only(text)
        )
        for f in per_file:
            try:
                rel = str(src.relative_to(target_dir))
            except ValueError:
                rel = str(src)
            findings.append(
                Finding(
                    severity=f.severity,
                    category=f.category,
                    file=rel,
                    line=f.line,
                    evidence=f.evidence,
                    fix=f.fix,
                ),
            )

    _persist(findings, target_dir)

    policy = _on_finding_policy(harness_config)
    _ = policy  # informational; callers decide blocking on high findings.

    return findings


def scan_prompt_injection_regex_only(text: str) -> list[Finding]:
    """Regex-only fallback (mirrors the legacy ``scan`` import path)."""
    from harness_maker.secscan.prompt_injection import scan as _regex_scan

    return _regex_scan(text)
