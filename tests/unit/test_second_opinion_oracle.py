"""Oracle gathering for the cross-model PIDA gate — path filtering, budget, redaction.

REVIEW M1 was a P0: the gathering step was PROSE that substituted an external model's `file`
field straight into `uv run pytest <paths>`. That field has no schema constraint and
`validate_payload` never inspects it, while `settings/*.json.j2` ship `Bash(uv run pytest:*)`
prefix rules that pre-approve arbitrary trailing arguments with no prompt. A value beginning
with `-` is therefore consumed as an OPTION, not a path — no shell metacharacter needed, no
permission prompt raised (`pytest --basetemp=<dir>` is documented to delete that directory).

The reviewer's rebuttal-in-advance is the reason this module exists: *"it's prose, not code"
does not soften the exposure — it removes the mitigation while leaving it.* The taint path was
real code; only the defence was prose. This repo already ruled that way once, when
`PLAN-second-opinion-invocation-and-slug-cap` ADR-001 moved the CLI calls out of prose after
four silent-skip bugs shipped there.

So the filter is code and these are its tests. The redaction tests double as the fix for M4:
a keyword line-regex missed PEM bodies, credentialed URLs, JWTs and env dumps, and the only
gate was `assert "REDACTED-LINE" in body` — a substring grep true of any render mentioning the
string.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.second_opinion_oracle import (
    BUDGET_PER_COMMAND,
    BUDGET_TOTAL,
    redact,
    safe_paths,
    truncate,
)

# ── path filtering (the P0) ────────────────────────────────────────────────────────────

_ALLOWED = {"src/a.py", "src/pkg/b.py"}


def test_option_shaped_path_is_rejected() -> None:
    """The P0 itself. `--basetemp=/tmp/x` needs no shell metacharacter and trips no prompt."""
    assert safe_paths(["--basetemp=/tmp/x"], _ALLOWED) == []
    assert safe_paths(["-p", "evil_module"], _ALLOWED) == []
    assert safe_paths(["-x"], _ALLOWED) == []


def test_traversal_and_absolute_paths_are_rejected() -> None:
    assert safe_paths(["../../etc/passwd"], _ALLOWED) == []
    assert safe_paths(["src/../../../etc/passwd"], _ALLOWED) == []
    assert safe_paths(["/etc/passwd"], _ALLOWED) == []


def test_paths_outside_the_changed_set_are_rejected() -> None:
    """Scoping to the diff is what stops a finding from steering the run at an arbitrary
    in-repo file; the prose version explicitly did NOT restrict to the changed set."""
    assert safe_paths(["src/unrelated.py"], _ALLOWED) == []


def test_allowed_paths_survive_and_are_deduped_in_order() -> None:
    assert safe_paths(["src/a.py", "src/a.py", "src/pkg/b.py"], _ALLOWED) == [
        "src/a.py",
        "src/pkg/b.py",
    ]


def test_non_string_and_empty_entries_are_dropped_not_crashed() -> None:
    """The payload is another model's JSON — `file` may be null, a number, or a dict."""
    assert safe_paths([None, 42, "", "   ", {"x": 1}, "src/a.py"], _ALLOWED) == ["src/a.py"]


def test_shell_metacharacters_are_rejected_even_though_argv_is_not_a_shell() -> None:
    """Defence in depth: the runner uses argv, but a path with `;`/`|`/`$(` is never a real
    changed file, so accepting one could only ever mean the filter was bypassed upstream."""
    for bad in ["src/a.py;rm -rf /", "src/a.py|cat", "$(id)", "src/a.py\nsrc/b.py"]:
        assert safe_paths([bad], _ALLOWED) == []


# ── redaction (M4) ─────────────────────────────────────────────────────────────────────


def test_pem_body_is_redacted_not_just_its_header() -> None:
    """Line-wise keyword matching is structurally wrong for a multi-line secret: only the
    `-----BEGIN` line matches, so the key material itself survived."""
    text = (
        "ok\n-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA7\n"
        "qx9\n-----END RSA PRIVATE KEY-----\nafter"
    )
    out = redact(text)
    assert "MIIEowIBAAKCAQEA7" not in out
    assert "qx9" not in out
    assert "ok" in out
    assert "after" in out


def test_credentialed_url_is_redacted() -> None:
    out = redact("fatal: could not read from https://ci:hunter2@internal.example/repo")
    assert "hunter2" not in out


def test_bare_jwt_is_redacted() -> None:
    out = redact("Authorization failed for eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc")
    assert "eyJhbGciOiJIUzI1NiJ9" not in out


def test_env_dump_values_are_redacted() -> None:
    """None of these contains `api_key`/`secret`/`token`/`password`, so the keyword filter
    passed every one of them through."""
    text = "\n".join(
        [
            "DATABASE_URL=postgres://u:p@h/db",
            "STRIPE_SK=sk_live_51H8xExampleKeyMaterial",
            "GH_PAT=ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        ]
    )
    out = redact(text)
    for secret in ("postgres://u:p@h/db", "sk_live_51H8xExampleKeyMaterial", "ghp_AAAA"):
        assert secret not in out


def test_ansi_is_stripped() -> None:
    assert "\x1b[31m" not in redact("\x1b[31mFAILED\x1b[0m tests/test_a.py")
    assert "FAILED" in redact("\x1b[31mFAILED\x1b[0m tests/test_a.py")


def test_ordinary_test_names_are_not_redacted() -> None:
    """The keyword filter's other half: it fired on benign words, redacting the decisive
    oracle line while the real secret survived. Value-shaped matching must not."""
    text = "FAILED tests/test_secret_rotation.py::test_token_refresh - AssertionError"
    out = redact(text)
    assert "test_secret_rotation" in out
    assert "test_token_refresh" in out


# ── budget / truncation ────────────────────────────────────────────────────────────────


def test_truncate_marks_visibly_and_respects_the_cap() -> None:
    out = truncate("x" * 5000, BUDGET_PER_COMMAND)
    assert len(out) <= BUDGET_PER_COMMAND
    assert "truncated" in out
    assert "chars" in out


def test_short_output_is_untouched() -> None:
    assert truncate("short", BUDGET_PER_COMMAND) == "short"


def test_budgets_are_ordered_sanely() -> None:
    assert BUDGET_PER_COMMAND < BUDGET_TOTAL


# ── the CLI contract ───────────────────────────────────────────────────────────────────


def test_cli_emits_labelled_blocks_and_drops_unsafe_paths(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """End-to-end: a findings payload in, labelled blocks out, with the option-shaped path
    gone and its finding recorded as having no oracle."""
    from harness_maker import second_opinion_oracle as mod

    monkeypatch.setattr(mod, "_changed_files", lambda _root: {"src/a.py"})
    # `_run_checks` was the pre-polyglot seam and is gone; `_run_argv` is the real one.
    # Patching a function nothing calls would leave this test green over any behaviour.
    monkeypatch.setattr(mod, "_load_toolchains", lambda _root: [])
    monkeypatch.setattr(mod, "_run_argv", lambda argv, root: f"ran {argv[2]}")

    payload = tmp_path / "f.json"
    payload.write_text(
        json.dumps(
            {
                "findings": [
                    {"id": "aaa1", "file": "src/a.py"},
                    {"id": "bbb2", "file": "--basetemp=/tmp/pwn"},
                    {"id": "ccc3", "file": None},
                ]
            }
        ),
        encoding="utf-8",
    )
    rc = mod.main(["--findings-file", str(payload), "--root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "aaa1" in out
    assert "--basetemp" not in out, "an option-shaped path reached the output"
    assert "bbb2" in out, "findings without an oracle must still be listed"
    assert "ccc3" in out, "findings without an oracle must still be listed"


def test_two_findings_on_one_path_produce_one_block(tmp_path: Path, monkeypatch, capsys) -> None:
    """The performance fix, made non-revertible.

    `gather` groups by path, not by finding: N findings over M files issue 3·M subprocesses
    instead of 3·N, each with its own 300 s timeout. The other CLI test monkeypatches
    `_run_checks` and would pass identically under the old per-finding shape, so it does not
    pin the fix. This does — and it also pins that the shared block still names BOTH ids, since
    the mode-B rubric may only adjudicate a finding whose id labels the block."""
    from harness_maker import second_opinion_oracle as mod

    calls: list[str] = []
    monkeypatch.setattr(mod, "_changed_files", lambda _root: {"src/a.py"})
    monkeypatch.setattr(mod, "_load_toolchains", lambda _root: [])
    # Seam moved from `_run_checks` (removed with the hardcoded triple) to `_run_argv`. The
    # property this pins is unchanged: ONE block per path, naming BOTH ids. Counting argv
    # calls would count 3 (one per role), so count the distinct paths they carry.
    monkeypatch.setattr(mod, "_run_argv", lambda argv, root: calls.append(argv[-1]) or "checked")

    payload = tmp_path / "f.json"
    payload.write_text(
        json.dumps(
            {"findings": [{"id": "one", "file": "src/a.py"}, {"id": "two", "file": "src/a.py"}]}
        ),
        encoding="utf-8",
    )
    assert mod.main(["--findings-file", str(payload), "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert set(calls) == {"src/a.py"}, f"checks ran on unexpected paths: {calls}"
    assert len(calls) == 3, f"expected the 3 default roles on one path, got {calls}"
    assert out.count("### oracle for") == 1
    assert "one" in out
    assert "two" in out


def test_cli_degrades_gracefully_on_a_bad_payload(tmp_path: Path, capsys) -> None:
    from harness_maker import second_opinion_oracle as mod

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert mod.main(["--findings-file", str(bad), "--root", str(tmp_path)]) == 0
    assert "no oracle gathered" in capsys.readouterr().err
