"""OSV.dev CVE crawler — POSTs package specs to ``https://api.osv.dev/v1/query``.

Phase 5 minimum scope: parse Python packages from ``uv.lock`` (TOML
``[[package]]`` entries) and query each. Packages may also be supplied
explicitly as ``[{"package": {"name": ..., "ecosystem": ...}, "version": ...}]``.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

import httpx

from harness_maker.models import CrawlItem

SOURCE = "osv_dev"
OSV_QUERY_URL = "https://api.osv.dev/v1/query"
DEFAULT_TIMEOUT = 10.0


def crawl(
    packages: list[dict[str, Any]] | None = None,
    client: httpx.Client | None = None,
) -> list[CrawlItem]:
    """Query OSV.dev for vulnerabilities matching ``packages``.

    ``packages`` is a list of OSV query dicts in the form::

        {"package": {"name": "<name>", "ecosystem": "<ecosystem>"}, "version": "<v>"}

    If ``packages`` is None or empty, returns an empty list (the caller
    should pass ``parse_uv_lock(path)`` to derive specs from a project).
    """
    if not packages:
        return []
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True)
    items: list[CrawlItem] = []
    try:
        for spec in packages:
            items.extend(_query_one(spec, client))
    finally:
        if owns_client:
            client.close()
    return items


def _query_one(spec: dict[str, Any], client: httpx.Client) -> list[CrawlItem]:
    try:
        response = client.post(OSV_QUERY_URL, json=spec)
    except httpx.HTTPError as exc:
        print(f"[osv_dev] HTTP error for {spec}: {exc}", file=sys.stderr)
        return []
    if response.status_code >= 400:
        print(
            f"[osv_dev] HTTP {response.status_code} for {spec}",
            file=sys.stderr,
        )
        return []
    try:
        payload = response.json()
    except ValueError as exc:
        print(f"[osv_dev] JSON decode error: {exc}", file=sys.stderr)
        return []
    if not isinstance(payload, dict):
        return []
    vulns = payload.get("vulns", [])
    if not isinstance(vulns, list):
        return []
    items: list[CrawlItem] = []
    pkg_meta = spec.get("package", {}) if isinstance(spec.get("package"), dict) else {}
    pkg_name = pkg_meta.get("name", "?")
    pkg_eco = pkg_meta.get("ecosystem", "?")
    version = spec.get("version", "?")
    for vuln in vulns:
        item = _to_item(vuln, pkg_name, pkg_eco, version)
        if item is not None:
            items.append(item)
    return items


def _to_item(
    vuln: dict[str, Any],
    pkg_name: str,
    pkg_eco: str,
    version: str,
) -> CrawlItem | None:
    if not isinstance(vuln, dict):
        return None
    vuln_id = vuln.get("id")
    if not vuln_id:
        return None
    summary = vuln.get("summary") or ""
    details = vuln.get("details") or ""
    return CrawlItem(
        source=SOURCE,
        item_id=str(vuln_id),
        title=f"{vuln_id}: {pkg_name} {version} ({pkg_eco})",
        summary=str(summary or details)[:1000],
        published=vuln.get("published") or vuln.get("modified"),
        metadata={
            "package": pkg_name,
            "ecosystem": pkg_eco,
            "version": version,
            "aliases": vuln.get("aliases", []),
            "severity": vuln.get("severity", []),
        },
    )


def parse_uv_lock(lock_path: Path | str) -> list[dict[str, Any]]:
    """Parse a ``uv.lock`` and return OSV query specs for every locked package.

    Returns ``[]`` if the file is missing or unreadable.
    """
    path = Path(lock_path)
    if not path.is_file():
        return []
    try:
        with path.open("rb") as fp:
            data = tomllib.load(fp)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"[osv_dev] uv.lock parse error: {exc}", file=sys.stderr)
        return []
    packages = data.get("package", [])
    if not isinstance(packages, list):
        return []
    specs: list[dict[str, Any]] = []
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        name = pkg.get("name")
        version = pkg.get("version")
        if not name or not version:
            continue
        specs.append(
            {
                "package": {"name": str(name), "ecosystem": "PyPI"},
                "version": str(version),
            }
        )
    return specs
