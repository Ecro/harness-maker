"""Executable-level oracles for the context-only Claude transport (AC-004..006)."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from harness_maker.claude_transport import ClaudeTransportError, invoke_claude

PAYLOAD = {"findings": [], "summary": "reviewed", "confidence": 0.8}
RESULT = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "structured_output": PAYLOAD,
}
HELP = "--print --safe-mode --tools --no-session-persistence --output-format --json-schema --model"
SECRET = "private-token-DO-NOT-EXPOSE"


def executable(tmp_path: Path, body: str, *, help_text: str = HELP, probe: str = "") -> str:
    script = tmp_path / "fake claude"
    script.write_text(
        f"#!{sys.executable}\nimport sys, os, json, time, subprocess\n"
        f"if '--help' in sys.argv:\n {probe or 'pass'}\n print({help_text!r})\n sys.exit(0)\n"
        + body
        + "\n"
    )
    script.chmod(0o700)
    return str(script)


def run_output(tmp_path: Path, raw: bytes, returncode: int = 0) -> dict[str, Any]:
    cli = executable(
        tmp_path, f"sys.stdin.read(); sys.stdout.buffer.write({raw!r}); sys.exit({returncode})"
    )
    return invoke_claude("supplied context", executable=cli, timeout=2)


def test_context_only_argv_stdin_and_isolated_cwd(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    prompt = "Unicode 검토; $(touch SHOULD_NOT_EXIST) `id`\nfull context"
    cli = executable(
        tmp_path,
        "captured = {'argv':sys.argv[1:], 'stdin':sys.stdin.read(), "
        "'cwd':os.getcwd(), 'home':os.environ.get('HOME')}; "
        f"json.dump(captured, open({str(capture)!r}, 'w')); "
        f"print({json.dumps(RESULT)!r})",
    )
    assert invoke_claude(prompt, model="chosen-model", executable=cli, timeout=2) == PAYLOAD
    observed = json.loads(capture.read_text())
    argv = observed["argv"]
    assert observed["stdin"] == prompt
    assert prompt not in argv
    assert "--safe-mode" in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert "--no-session-persistence" in argv
    assert "--print" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--model") + 1] == "chosen-model"
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert "findings" in schema["properties"]
    assert observed["home"] == os.environ.get("HOME")
    assert Path(observed["cwd"]) != Path.cwd()
    assert not Path(observed["cwd"]).exists()
    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()


@pytest.mark.parametrize(
    "flag", ["--safe-mode", "--tools", "--json-schema", "--no-session-persistence"]
)
def test_missing_isolation_capability_fails_closed(tmp_path: Path, flag: str) -> None:
    marker = tmp_path / "invoked"
    cli = executable(
        tmp_path, f"open({str(marker)!r}, 'w').write('unsafe')", help_text=HELP.replace(flag, "")
    )
    with pytest.raises(ClaudeTransportError, match="^unsupported_cli$"):
        invoke_claude("context", executable=cli, timeout=2)
    assert not marker.exists()


@pytest.mark.parametrize("event_array", [False, True])
@pytest.mark.parametrize(
    "findings",
    [
        [],
        [
            {
                "severity": "high",
                "message": "Untrusted command execution",
                "evidence": "shell=True accepts external input",
                "file": "src/runner.py",
                "line": 17,
            }
        ],
    ],
)
def test_result_object_and_event_array(
    tmp_path: Path, event_array: bool, findings: list[dict[str, Any]]
) -> None:
    payload = {**PAYLOAD, "findings": findings}
    result = {**RESULT, "structured_output": payload}
    framing = [{"type": "system", "subtype": "init"}, result] if event_array else result
    assert run_output(tmp_path, json.dumps(framing).encode()) == payload


@pytest.mark.parametrize(
    ("framing", "code"),
    [
        ([], "invalid_envelope"),
        ([{"type": "system"}], "invalid_envelope"),
        ([RESULT, RESULT], "invalid_envelope"),
        ([RESULT, {"type": "system", "subtype": "late"}], "invalid_envelope"),
        ([RESULT, {**RESULT, "is_error": True}], "invalid_envelope"),
        ([42, RESULT], "invalid_envelope"),
        ({**RESULT, "structured_output": {"findings": [], "summary": "x"}}, "invalid_payload"),
        ({**RESULT, "is_error": True}, "provider_failed"),
        ({"type": "result", "subtype": "success", "is_error": False}, "missing_payload"),
    ],
)
def test_ambiguous_or_invalid_provider_results(tmp_path: Path, framing: Any, code: str) -> None:
    with pytest.raises(ClaudeTransportError) as caught:
        run_output(tmp_path, json.dumps(framing).encode())
    assert caught.value.code == code


@pytest.mark.parametrize("raw", [b'{"type":"result","type":"result"}', b"[NaN]", b"not JSON"])
def test_malformed_json_not_normalized_away(tmp_path: Path, raw: bytes) -> None:
    with pytest.raises(ClaudeTransportError, match="^invalid_json$"):
        run_output(tmp_path, raw)


def test_invalid_encoding(tmp_path: Path) -> None:
    with pytest.raises(ClaudeTransportError, match="^invalid_encoding$"):
        run_output(tmp_path, b"\xff")


def test_missing_executable(tmp_path: Path) -> None:
    with pytest.raises(ClaudeTransportError, match="^cli_not_found$"):
        invoke_claude("context", executable=str(tmp_path / "absent"), timeout=1)


def test_auth_or_config_failure_never_exposes_diagnostics(tmp_path: Path) -> None:
    cli = executable(tmp_path, f"sys.stderr.write({SECRET!r}); print({SECRET!r}); sys.exit(1)")
    with pytest.raises(ClaudeTransportError) as caught:
        invoke_claude("context", executable=cli, timeout=2)
    assert caught.value.code == "process_failed"
    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)


def test_input_cap_prevents_process_start(tmp_path: Path) -> None:
    marker = tmp_path / "probe-started"
    cli = executable(tmp_path, "pass", probe=f"open({str(marker)!r}, 'w').write('started')")
    with pytest.raises(ClaudeTransportError, match="^input_too_large$"):
        invoke_claude("한" * 10, executable=cli, max_input_bytes=20)
    assert not marker.exists()


@pytest.mark.parametrize(
    ("stream", "code"), [("stdout", "output_too_large"), ("stderr", "stderr_too_large")]
)
def test_flood_is_bounded_before_deadline(tmp_path: Path, stream: str, code: str) -> None:
    cli = executable(
        tmp_path, f"while True: sys.{stream}.buffer.write(b'x'*65536); sys.{stream}.flush()"
    )
    started = time.monotonic()
    with pytest.raises(ClaudeTransportError) as caught:
        invoke_claude(
            "context", executable=cli, timeout=3, max_stdout_bytes=8192, max_stderr_bytes=8192
        )
    assert caught.value.code == code
    assert time.monotonic() - started < 2


def test_probe_is_also_bounded(tmp_path: Path) -> None:
    cli = executable(tmp_path, "pass", probe="time.sleep(10)")
    started = time.monotonic()
    with pytest.raises(ClaudeTransportError, match="^timeout$"):
        invoke_claude("context", executable=cli, timeout=0.25)
    assert time.monotonic() - started < 2


def running(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().split(")", 1)[1].split()[0]
    except FileNotFoundError:
        return False
    return state not in {"Z", "X"}


@pytest.mark.parametrize("parent_exit", [False, True])
def test_deadline_kills_children_even_with_inherited_pipes(
    tmp_path: Path, parent_exit: bool
) -> None:
    pid_file = tmp_path / "child.pid"
    cli = executable(
        tmp_path,
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        f"open({str(pid_file)!r}, 'w').write(str(child.pid)); "
        + ("sys.exit(0)" if parent_exit else "time.sleep(30)"),
    )
    started = time.monotonic()
    try:
        with pytest.raises(ClaudeTransportError, match="^timeout$"):
            invoke_claude("context", executable=cli, timeout=2)
        assert time.monotonic() - started < 5
        child_pid = int(pid_file.read_text())
        deadline = time.monotonic() + 1
        while running(child_pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not running(child_pid)
    finally:
        if pid_file.exists() and running(int(pid_file.read_text())):
            os.kill(int(pid_file.read_text()), 9)


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True])
def test_invalid_deadline_rejected(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        invoke_claude("context", timeout=timeout)


def test_success_cleans_surviving_child_with_closed_pipes(tmp_path: Path) -> None:
    pid_file = tmp_path / "success-child.pid"
    cli = executable(
        tmp_path,
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        f"open({str(pid_file)!r}, 'w').write(str(child.pid)); "
        f"sys.stdin.read(); print({json.dumps(RESULT)!r})",
    )
    try:
        assert invoke_claude("context", executable=cli, timeout=2) == PAYLOAD
        child_pid = int(pid_file.read_text())
        deadline = time.monotonic() + 1
        while running(child_pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not running(child_pid)
    finally:
        if pid_file.exists() and running(int(pid_file.read_text())):
            os.kill(int(pid_file.read_text()), signal.SIGKILL)


def test_external_caller_cancellation_cleans_owned_processes(tmp_path: Path) -> None:
    pid_file = tmp_path / "cancel-pids.json"
    cli = executable(
        tmp_path,
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"with open({str(pid_file.with_suffix('.tmp'))!r}, 'w') as stream:\n"
        " json.dump([os.getpid(), child.pid], stream)\n"
        f"os.replace({str(pid_file.with_suffix('.tmp'))!r}, {str(pid_file)!r})\n"
        "time.sleep(30)",
    )
    driver = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from harness_maker.claude_transport import invoke_claude; "
            f"invoke_claude('context', executable={cli!r}, timeout=20)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    owned: list[int] = []
    try:
        ready_deadline = time.monotonic() + 5
        while not pid_file.exists() and time.monotonic() < ready_deadline:
            assert driver.poll() is None, "caller exited before invocation"
            time.sleep(0.01)
        assert pid_file.exists(), "synthetic provider never started"
        owned = json.loads(pid_file.read_text())
        driver.send_signal(signal.SIGINT)
        driver.communicate(timeout=3)
        assert driver.returncode != 0
        cleanup_deadline = time.monotonic() + 1
        while any(running(pid) for pid in owned) and time.monotonic() < cleanup_deadline:
            time.sleep(0.01)
        assert all(not running(pid) for pid in owned)
    finally:
        if driver.poll() is None:
            driver.kill()
        driver.communicate(timeout=3)
        for pid in owned:
            if running(pid):
                os.kill(pid, signal.SIGKILL)
