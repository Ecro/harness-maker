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
    if not target_dir.exists():
        return []
    return _scan_paths(target_dir, _iter_files(target_dir))


def scan_files(target_dir: Path, rel_paths: list[str]) -> list[Finding]:
    """Scan exactly these files (relative to ``target_dir``), with the same filters as `scan`.

    `hm check` passes git's own file list, so an ignored `.worktrees/` copy of the tree is
    never walked and the scan matches the snapshot it is reported beside.
    """
    files = [target_dir / rel for rel in rel_paths]
    return _scan_paths(
        target_dir,
        [
            f
            for f in files
            if f.is_file()
            and _should_scan(f)
            and not any(part in _SKIP_DIR_NAMES for part in f.relative_to(target_dir).parts)
        ],
    )


def _scan_paths(target_dir: Path, paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for f in paths:
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
