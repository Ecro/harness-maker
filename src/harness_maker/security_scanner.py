"""Security scanner orchestrator — invokes 5 gates and persists findings.

Returns aggregated findings; persists to ``.claude/observability/security/findings-<date>.jsonl``.
The ``on_finding.high`` policy in ``harness_config.security`` controls semantics:
- ``"warn"``  — return findings, log but do not raise.
- ``"block"`` — return findings; caller should treat non-empty list as a build failure.
- ``"allow"`` — return findings (caller may ignore).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker.models import Finding
from harness_maker.secscan import (
    scan_dependency_cves,
    scan_hook_injection,
    scan_permissions,
    scan_prompt_injection,
    scan_secrets,
)


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


def scan_all(
    target_dir: Path,
    harness_config: dict[str, Any] | None = None,
) -> list[Finding]:
    """Run all 5 security gates against ``target_dir``; persist + return findings."""
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

    # Prompt-injection scan: walk markdown files in target_dir for hidden patterns.
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
        for f in scan_prompt_injection(text):
            try:
                rel = str(src.relative_to(target_dir))
            except ValueError:
                rel = str(src)
            # Re-bind the file field (per-source).
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
    # Policy is informational at this layer — we always return findings.
    # The caller (CLI / autoloop driver) inspects the policy to decide whether
    # a non-empty high-severity list aborts the run.
    _ = policy

    return findings
