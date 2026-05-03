"""Statusline tests (per amendments §C/§D/§E/§I)."""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker import statusline

LINE_RE = re.compile(
    r"^[^|]+ \| (Side|Production) \| 🪙\d+% \| 🎯\d+ \| 🔄\d+d$",
)


def _setup_minimal_project(target: Path, *, preset: str = "Side") -> None:
    claude = target / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(f"preset: {preset}\nlocale: ko\n")
    obs = claude / "observability"
    obs.mkdir(parents=True, exist_ok=True)
    metrics = obs / "metrics.jsonl"
    # 5 mock entries with mixed cache hits
    lines = []
    for i in range(5):
        lines.append(
            json.dumps(
                {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_tokens": 50,
                    "tool_name": f"Tool{i}",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                },
            ),
        )
    metrics.write_text("\n".join(lines) + "\n")
    refresh = obs / "refresh"
    refresh.mkdir(parents=True, exist_ok=True)
    (refresh / "raw-2026-01-01.jsonl").write_text("{}\n")


def test_format_with_mock_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _setup_minimal_project(tmp_path)
    payload = {"workspace": {"current_dir": str(tmp_path)}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = statusline.main()
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert LINE_RE.match(out), f"Unexpected statusline: {out!r}"
    assert "Side" in out


def test_no_claude_dir_graceful_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {"workspace": {"current_dir": str(tmp_path)}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = statusline.main()
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert LINE_RE.match(out), f"Unexpected fallback: {out!r}"
    assert "🪙0%" in out
    assert "🔄999d" in out


def test_production_preset_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _setup_minimal_project(tmp_path, preset="Production")
    payload = {"workspace": {"current_dir": str(tmp_path)}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    statusline.main()
    out = capsys.readouterr().out.strip()
    assert "Production" in out
    assert LINE_RE.match(out)


def test_malformed_stdin_falls_back_to_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("garbage{{{"))
    rc = statusline.main()
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert LINE_RE.match(out), f"Unexpected output: {out!r}"


def test_subprocess_entry_point(tmp_path: Path) -> None:
    _setup_minimal_project(tmp_path)
    payload = {"workspace": {"current_dir": str(tmp_path)}}
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.statusline"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    out = proc.stdout.strip()
    assert LINE_RE.match(out), f"Unexpected output: {out!r}"


def test_format_line_helper() -> None:
    from harness_maker.models import Preset

    line = statusline.format_line("myproj", Preset.SIDE, 42, 80, 3)
    assert LINE_RE.match(line)
    assert "myproj" in line
    assert "🪙42%" in line
    assert "🎯80" in line
    assert "🔄3d" in line
