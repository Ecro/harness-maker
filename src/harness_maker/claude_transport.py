"""Bounded, context-only Claude Code subprocess transport.

Authentication remains owned by the CLI. Every invocation uses a fresh directory,
capability-checked safe mode and a process group that is cleaned on every exit.
"""

import json
import math
import os
import re
import selectors
import shutil
import signal
import subprocess
import time
from contextlib import suppress
from importlib.resources import files
from tempfile import TemporaryDirectory
from typing import Any, NoReturn

from harness_maker.claude_response import ClaudeResponseError, parse_response

_MAX_BYTES = 1024 * 1024
_REQUIRED = (
    "--print",
    "--safe-mode",
    "--tools",
    "--no-session-persistence",
    "--output-format",
    "--json-schema",
)


class ClaudeTransportError(ValueError):
    """Fixed failure code, never provider diagnostics or supplied context."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _run(
    argv: list[str],
    data: bytes,
    *,
    cwd: str,
    deadline: float,
    stdout_limit: int,
    stderr_limit: int,
) -> tuple[bytes, int]:
    if time.monotonic() >= deadline:
        raise ClaudeTransportError("timeout")
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            start_new_session=True,
            shell=False,
        )
    except FileNotFoundError:
        raise ClaudeTransportError("cli_not_found") from None
    except OSError:
        raise ClaudeTransportError("process_failed") from None
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    output = bytearray()
    stderr_size = 0
    offset = 0
    try:
        with selectors.DefaultSelector() as selector:
            for stream, label in ((process.stdout, "stdout"), (process.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, label)
            if data:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            else:
                process.stdin.close()
            while selector.get_map() or process.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ClaudeTransportError("timeout")
                for key, _ in selector.select(min(remaining, 0.1)):
                    if key.data == "stdin":
                        try:
                            offset += os.write(key.fd, data[offset : offset + 65536])
                        except BrokenPipeError:
                            offset = len(data)
                        except BlockingIOError:
                            continue
                        if offset == len(data):
                            selector.unregister(key.fd)
                            process.stdin.close()
                        continue
                    size = len(output) if key.data == "stdout" else stderr_size
                    limit = stdout_limit if key.data == "stdout" else stderr_limit
                    try:
                        chunk = os.read(key.fd, min(65536, limit - size + 1))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fd)
                        continue
                    if size + len(chunk) > limit:
                        code = "output_too_large" if key.data == "stdout" else "stderr_too_large"
                        raise ClaudeTransportError(code)
                    if key.data == "stdout":
                        output.extend(chunk)
                    else:
                        stderr_size += len(chunk)
        return bytes(output), process.wait(timeout=max(0.001, deadline - time.monotonic()))
    finally:
        # The leader may have exited while a child still holds a pipe, or may have
        # closed its pipes before exiting. Kill the whole owned group even on success.
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
        process.wait()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _invalid_constant(value: str) -> NoReturn:
    raise ValueError("nonfinite JSON")


def _normalize(raw: bytes, limit: int) -> dict[str, Any]:
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ClaudeTransportError("invalid_encoding") from None
    try:
        envelope = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (ValueError, RecursionError):
        raise ClaudeTransportError("invalid_json") from None
    if isinstance(envelope, list):
        if (
            not envelope
            or any(not isinstance(event, dict) for event in envelope)
            or sum(event.get("type") == "result" for event in envelope) != 1
            or envelope[-1].get("type") != "result"
        ):
            raise ClaudeTransportError("invalid_envelope")
        envelope = envelope[-1]
    try:
        # Re-encoding must not impose a second byte budget on equivalent JSON;
        # escaping Unicode/whitespace can legitimately change representation size.
        normalized = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        return parse_response(normalized, returncode=0, max_bytes=max(limit, len(normalized)))
    except ClaudeResponseError as exc:
        raise ClaudeTransportError(exc.code) from None
    except (ValueError, UnicodeError, RecursionError):
        raise ClaudeTransportError("invalid_json") from None


def invoke_claude(
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = 300,
    executable: str = "claude",
    max_input_bytes: int = _MAX_BYTES,
    max_stdout_bytes: int = _MAX_BYTES,
    max_stderr_bytes: int = _MAX_BYTES,
) -> dict[str, Any]:
    """Return strictly validated findings or a fixed-code transport failure.

    The single deadline includes capability probing and response collection.
    KeyboardInterrupt/caller cancellation propagates after process-group cleanup.
    """
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    for limit in (max_input_bytes, max_stdout_bytes, max_stderr_bytes):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("byte limits must be positive integers")
    if len(prompt) > max_input_bytes:
        raise ClaudeTransportError("input_too_large")
    data = prompt.encode("utf-8")
    if len(data) > max_input_bytes:
        raise ClaudeTransportError("input_too_large")
    resolved = shutil.which(executable)
    if resolved is None:
        raise ClaudeTransportError("cli_not_found")
    resolved = os.path.abspath(resolved)
    deadline = time.monotonic() + timeout
    schema = (
        files("harness_maker")
        .joinpath("templates/schemas/second-opinion-finding.schema.json")
        .read_text(encoding="utf-8")
    )
    with TemporaryDirectory(prefix="hm-claude-") as cwd:
        help_raw, help_status = _run(
            [resolved, "--help"],
            b"",
            cwd=cwd,
            deadline=deadline,
            stdout_limit=max_stdout_bytes,
            stderr_limit=max_stderr_bytes,
        )
        if help_status != 0:
            raise ClaudeTransportError("process_failed")
        help_text = help_raw.decode("utf-8", errors="replace")
        required = (*_REQUIRED, "--model") if model is not None else _REQUIRED
        if any(
            re.search(r"(?<![\w-])" + re.escape(flag) + r"(?=[\s,=]|$)", help_text) is None
            for flag in required
        ):
            raise ClaudeTransportError("unsupported_cli")
        argv = [
            resolved,
            "--print",
            "--safe-mode",
            "--tools",
            "",
            "--no-session-persistence",
            "--output-format",
            "json",
            "--json-schema",
            schema,
        ]
        if model is not None:
            argv.extend(["--model", model])
        raw, status = _run(
            argv,
            data,
            cwd=cwd,
            deadline=deadline,
            stdout_limit=max_stdout_bytes,
            stderr_limit=max_stderr_bytes,
        )
    if status != 0:
        raise ClaudeTransportError("process_failed")
    return _normalize(raw, max_stdout_bytes)
