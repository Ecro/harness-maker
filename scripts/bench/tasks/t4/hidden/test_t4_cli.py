"""Hidden tests for t4: CLI --sum and stdin '-'."""

import io
import subprocess
import sys

import pytest
from timeparse.cli import main


def _run(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    stdin: str = "",
) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_sum(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(["--sum", "1h", "30m"], capsys, monkeypatch) == (0, "5400\n", "")


def test_sum_after_args(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(["1h", "30m", "--sum"], capsys, monkeypatch)[:2] == (0, "5400\n")


def test_sum_single(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(["--sum", "45s"], capsys, monkeypatch)[:2] == (0, "45\n")


def test_stdin_sum(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(["-", "--sum"], capsys, monkeypatch, "1m\n\n2m\n")[:2] == (0, "180\n")


def test_stdin_lines(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    code, out, _ = _run(["-"], capsys, monkeypatch, "  1m  \n\n   \n2s\n")
    assert (code, out.split()) == (0, ["60", "2"])


def test_stdin_mixed_keeps_order(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, out, _ = _run(["1s", "-", "3s"], capsys, monkeypatch, "2s\n")
    assert (code, out.split()) == (0, ["1", "2", "3"])


def test_reports_every_invalid(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, out, err = _run(["1h", "x", "2q"], capsys, monkeypatch)
    assert code == 2
    assert out == ""
    assert err.splitlines() == ["error: invalid duration: 'x'", "error: invalid duration: '2q'"]


def test_invalid_with_sum_prints_nothing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, out, err = _run(["--sum", "1h", "bad"], capsys, monkeypatch)
    assert (code, out) == (2, "")
    assert "'bad'" in err


def test_invalid_stdin_lines_reported_stripped(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, out, err = _run(["-"], capsys, monkeypatch, "1m\n  zz  \nyy\n")
    assert (code, out) == (2, "")
    assert err.splitlines() == ["error: invalid duration: 'zz'", "error: invalid duration: 'yy'"]


def test_plain_output_unchanged(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, out, _ = _run(["1h", "30s"], capsys, monkeypatch)
    assert (code, out.split()) == (0, ["3600", "30"])


def test_subprocess_stdin_dash() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "timeparse.cli", "-", "--sum"],
        input="1h\n1m\n",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert (proc.returncode, proc.stdout) == (0, "3660\n")
