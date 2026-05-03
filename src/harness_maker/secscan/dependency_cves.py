"""Dependency CVE gate — query OSV.dev for packages declared in uv.lock / pyproject.toml.

The query function is injectable for tests. Default uses ``crawler.osv_dev.crawl``.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from harness_maker.crawler import osv_dev
from harness_maker.models import CrawlItem, Finding

QueryFn = Callable[[list[dict[str, Any]]], list[CrawlItem]]


def _default_query(specs: list[dict[str, Any]]) -> list[CrawlItem]:
    return osv_dev.crawl(packages=specs)


def _parse_pyproject(pyproject: Path) -> list[dict[str, Any]]:
    """Extract [project].dependencies from pyproject.toml as best-effort specs.

    pyproject.toml does not pin versions in most cases, so ``version`` may be
    ``"*"`` — OSV will still match by name + ecosystem in many cases.
    """
    try:
        with pyproject.open("rb") as fp:
            data = tomllib.load(fp)
    except (OSError, tomllib.TOMLDecodeError):
        return []
    project = data.get("project", {})
    deps = project.get("dependencies", [])
    if not isinstance(deps, list):
        return []
    specs: list[dict[str, Any]] = []
    for dep in deps:
        if not isinstance(dep, str):
            continue
        # crude split on version operator
        name = dep
        for op in (">=", "<=", "==", "~=", "!=", ">", "<", " ", "["):
            if op in name:
                name = name.split(op, 1)[0]
                break
        name = name.strip()
        if name:
            specs.append(
                {"package": {"name": name, "ecosystem": "PyPI"}, "version": "*"},
            )
    return specs


def _classify_severity(item: CrawlItem) -> str:
    """Map OSV severity to high/medium/low buckets via CVSS score thresholds."""
    sev_list = item.metadata.get("severity")
    if not isinstance(sev_list, list):
        return "low"
    max_score = 0.0
    for sev in sev_list:
        if not isinstance(sev, dict):
            continue
        score_field = sev.get("score")
        if score_field is None:
            continue
        try:
            score = float(score_field)
        except (TypeError, ValueError):
            # CVSS vector strings like "CVSS:3.1/AV:N/..." — skip; not a numeric score.
            continue
        max_score = max(max_score, score)
    if max_score >= 7.0:
        return "high"
    if max_score >= 4.0:
        return "medium"
    return "low"


def scan(target_dir: Path, query_fn: QueryFn | None = None) -> list[Finding]:
    """Scan dependency manifests for known CVEs.

    Args:
        target_dir: Project root containing ``uv.lock`` or ``pyproject.toml``.
        query_fn:   Override OSV query (used by tests). Default = osv_dev.crawl.
    """
    findings: list[Finding] = []
    if not target_dir.exists():
        return findings

    qfn = query_fn if query_fn is not None else _default_query

    specs: list[dict[str, Any]] = []
    lock = target_dir / "uv.lock"
    pyproject = target_dir / "pyproject.toml"
    if lock.exists():
        specs = osv_dev.parse_uv_lock(lock)
    elif pyproject.exists():
        specs = _parse_pyproject(pyproject)

    if not specs:
        return findings

    items = qfn(specs)
    for item in items:
        severity = _classify_severity(item)
        pkg = item.metadata.get("package", "?")
        version = item.metadata.get("version", "?")
        ecosystem = item.metadata.get("ecosystem", "?")
        findings.append(
            Finding(
                severity=severity,
                category="cve",
                file=lock.name if lock.exists() else pyproject.name,
                line=0,
                evidence=f"{item.item_id}: {pkg} {version} ({ecosystem})",
                fix=f"Upgrade {pkg} to a version unaffected by {item.item_id}.",
            ),
        )
    return findings
