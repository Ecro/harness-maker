"""OSV.dev crawler tests — POSTs mocked via httpx.MockTransport."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from harness_maker.crawler import osv_dev

SAMPLE_OSV_RESPONSE = {
    "vulns": [
        {
            "id": "GHSA-aaaa-bbbb-cccc",
            "summary": "Demo vulnerability summary",
            "details": "More details here",
            "published": "2026-01-01T00:00:00Z",
            "modified": "2026-02-01T00:00:00Z",
            "aliases": ["CVE-2026-00001"],
            "severity": [{"type": "CVSS_V3", "score": "7.5"}],
        }
    ]
}


def _client_returning(payload: object, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "osv.dev" in request.url.host
        return httpx.Response(status, content=json.dumps(payload).encode())

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_crawl_returns_vulnerabilities() -> None:
    client = _client_returning(SAMPLE_OSV_RESPONSE)
    specs = [
        {"package": {"name": "requests", "ecosystem": "PyPI"}, "version": "2.0.0"}
    ]
    items = osv_dev.crawl(packages=specs, client=client)

    assert len(items) == 1
    item = items[0]
    assert item.source == "osv_dev"
    assert item.item_id == "GHSA-aaaa-bbbb-cccc"
    assert "requests" in item.title
    assert item.metadata["package"] == "requests"
    assert item.metadata["ecosystem"] == "PyPI"


def test_crawl_with_no_packages_returns_empty() -> None:
    items = osv_dev.crawl(packages=None)
    assert items == []
    items = osv_dev.crawl(packages=[])
    assert items == []


def test_crawl_handles_http_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    items = osv_dev.crawl(
        packages=[{"package": {"name": "x", "ecosystem": "PyPI"}, "version": "0.1"}],
        client=client,
    )
    assert items == []


def test_parse_uv_lock_extracts_packages(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text(
        '''
version = 1

[[package]]
name = "requests"
version = "2.32.0"

[[package]]
name = "pydantic"
version = "2.7.1"

[[package]]
name = "incomplete"
'''.strip()
    )
    specs = osv_dev.parse_uv_lock(lock)
    names = {s["package"]["name"] for s in specs}
    assert names == {"requests", "pydantic"}
    assert all(s["package"]["ecosystem"] == "PyPI" for s in specs)


def test_parse_uv_lock_missing_file_returns_empty(tmp_path: Path) -> None:
    assert osv_dev.parse_uv_lock(tmp_path / "nope.lock") == []
