"""Secrets gate — regex-based detection of common secret patterns in source files.

Patterns adapted from gitleaks catalog (high-precision subset):
- AWS access keys: ``AKIA[0-9A-Z]{16}``
- GitHub PAT: ``ghp_[A-Za-z0-9]{36}``
- Anthropic API key: ``sk-ant-[A-Za-z0-9_-]{95,}``
- Generic ``.env``-style ``KEY=value`` for password/secret/key/token names
"""

from __future__ import annotations

import re
from pathlib import Path

from harness_maker.models import Finding

_SCAN_EXTENSIONS = {".py", ".js", ".ts", ".md", ".json", ".env", ".yaml", ".yml", ".toml"}
_SCAN_FILENAMES = {".env"}
_SKIP_DIR_NAMES = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "high"),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), "high"),
    ("anthropic_api_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{95,}\b"), "high"),
    (
        "env_secret",
        re.compile(
            r"^\s*(?P<key>[A-Z][A-Z0-9_]*"
            r"(?:PASSWORD|SECRET|TOKEN|API_KEY|APIKEY|PRIVATE_KEY))\s*=\s*"
            r"(?P<val>['\"]?[^'\"\n#]{8,}['\"]?)",
            re.MULTILINE,
        ),
        "high",
    ),
]


def _should_scan(path: Path) -> bool:
    if path.name in _SCAN_FILENAMES:
        return True
    return path.suffix.lower() in _SCAN_EXTENSIONS


def _iter_files(target_dir: Path) -> list[Path]:
    out: list[Path] = []
    for p in target_dir.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in p.parts):
            continue
        if _should_scan(p):
            out.append(p)
    return out


def scan(target_dir: Path) -> list[Finding]:
    """Walk ``target_dir`` and return findings for any matching secret pattern."""
    findings: list[Finding] = []
    if not target_dir.exists():
        return findings
    for f in _iter_files(target_dir):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for category, pattern, severity in _PATTERNS:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                evidence = match.group(0)
                # Truncate / mask the evidence to avoid echoing full secrets in logs.
                if len(evidence) > 32:
                    evidence = evidence[:8] + "..." + evidence[-4:]
                try:
                    rel = str(f.relative_to(target_dir))
                except ValueError:
                    rel = str(f)
                findings.append(
                    Finding(
                        severity=severity,
                        category="secrets",
                        file=rel,
                        line=line_no,
                        evidence=f"{category}: {evidence}",
                        fix=f"Remove the {category} from source; rotate the credential.",
                    ),
                )
    return findings
