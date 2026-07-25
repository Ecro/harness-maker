"""Second-opinion invocation contract — PLAN-second-opinion-invocation-and-slug-cap.

The two CLI invocations lived in rendered prose, which has no execution surface:
render tests can only grep its text. Four distinct silent-skip bugs shipped that
way. This module is the contract; these tests are the surface it now has.

Two dimensions here are deliberately NOT covered by the golden-argv assertions,
because argv is structurally blind to them: how the prompt REACHES the process
(`input=` vs an argv value) and where the payload is READ BACK from. Both get
their own call-kwargs assertions — a correct argv with an unwired stdin is
exactly how the codex vote would die again.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import second_opinion_invoke as soi

# ── fixtures ─────────────────────────────────────────────────────────────────


def _write_harness_yaml(base: Path, *, antigravity_model: str, hermetic: bool) -> None:
    """A harness.yaml carrying the provenance frontmatter the renderer emits, so the
    loader is exercised against the real multi-document shape (a single
    `yaml.safe_load` rejects it — CLAUDE.md checkpoint 2)."""
    cfg = base / ".claude" / "harness.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "---\n"
        "generated_by: harness-maker\n"
        "content_hash: deadbeef\n"
        "---\n"
        "second_opinion:\n"
        '  models: ["codex", "antigravity"]\n'
        "  codex:\n"
        f"    hermetic: {str(hermetic).lower()}\n"
        '    output_schema_path: ".claude/schemas/second-opinion-finding.schema.json"\n'
        "  antigravity:\n"
        f'    model: "{antigravity_model}"\n',
        encoding="utf-8",
    )


def _write_schema(base: Path) -> Path:
    p = base / ".claude" / "schemas" / "second-opinion-finding.schema.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"type": "object"}', encoding="utf-8")
    return p


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repo with one commit — `resolve_base_root` parses real `git`
    stdout, and this project has a recorded failure (`_check_pytest_collect`) from
    mocking an external command's output everywhere and never testing the real one."""
    base = tmp_path / "repo"
    base.mkdir()
    _git(base, "init", "-q", "-b", "main")
    _git(base, "config", "user.email", "t@example.com")
    _git(base, "config", "user.name", "t")
    (base / "README.md").write_text("x\n", encoding="utf-8")
    _git(base, "add", "-A")
    _git(base, "commit", "-qm", "init")
    return base


def _valid_payload() -> dict[str, Any]:
    return {
        "findings": [
            {
                "severity": "high",
                "message": "a real finding",
                "evidence": "e",
                "file": "a.py",
                "line": 3,
            }
        ],
        "summary": "s",
        "confidence": 0.9,
    }


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


_REAL_RUN = subprocess.run


def _run_with(monkeypatch: pytest.MonkeyPatch, fake: Any) -> None:
    """Patch the CLI call while letting the invoker's own `git` probes reach real git.

    `soi.subprocess` IS the global module object — the module under test binds it with
    a plain `import subprocess` — so setting `.run` on it rebinds process-wide,
    including `resolve_base_root`'s `git worktree list --porcelain`. Undelegated, the
    fake answers that probe with a findings payload, base-root resolution parses JSON
    as porcelain and returns a nonsense path, and any assertion downstream of it is
    measuring garbage. Delegating `git` keeps the mock on the subject of the test.
    """

    def dispatch(argv: list[str], **kwargs: Any) -> Any:
        if argv and argv[0] == "git":
            return _REAL_RUN(argv, **kwargs)
        return fake(argv, **kwargs)

    monkeypatch.setattr(soi.subprocess, "run", dispatch)


# ── base-root resolution (5 cases, against REAL git) ─────────────────────────


def test_base_root_from_base_checkout(repo: Path) -> None:
    assert soi.resolve_base_root(repo) == repo.resolve()


def test_base_root_from_linked_worktree(repo: Path) -> None:
    wt = repo / ".worktrees" / "slug"
    _git(repo, "worktree", "add", "-q", "-b", "hm/slug", str(wt))
    # The dimension that killed H1: cwd inside a worktree must still resolve to base.
    assert soi.resolve_base_root(wt) == repo.resolve()


def test_base_root_from_nested_subdirectory(repo: Path) -> None:
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)
    assert soi.resolve_base_root(nested) == repo.resolve()


def test_base_root_with_separate_git_dir(tmp_path: Path) -> None:
    # `--git-common-dir`'s parent is NOT the checkout root here; the porcelain-first
    # algorithm must not depend on that identity.
    work = tmp_path / "work"
    gitdir = tmp_path / "elsewhere.git"
    work.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", "--separate-git-dir", str(gitdir), str(work)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert soi.resolve_base_root(work) == work.resolve()


def test_base_root_falls_back_to_cwd_outside_git(tmp_path: Path) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    assert soi.resolve_base_root(plain) == plain.resolve()


# ── config resolution ────────────────────────────────────────────────────────


def test_load_config_reads_per_model_subblocks_from_provenance_yaml(repo: Path) -> None:
    # Parse-level only: the renderer prefixes harness.yaml with a provenance document,
    # so a single `yaml.safe_load` rejects it (CLAUDE.md checkpoint 2).
    _write_harness_yaml(repo, antigravity_model="Gemini 3.1 Pro (Low)", hermetic=False)

    cfg = soi.load_config(repo)

    assert cfg["antigravity"]["model"] == "Gemini 3.1 Pro (Low)"
    assert cfg["codex"]["hermetic"] is False


def test_config_survives_a_worktree_cwd_with_no_claude_dir(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The dimension the name claims must be exercised with a REAL cwd: passing an
    # already-resolved base root cannot distinguish a base-rooted load from a
    # cwd-relative one. A cwd-relative load here finds nothing and silently falls back
    # to defaults — the user's configured model replaced while still reporting
    # `invoked`, which is H2's shape in the config dimension.
    _write_harness_yaml(repo, antigravity_model="Gemini 3.1 Pro (Low)", hermetic=False)
    wt = repo / ".worktrees" / "slug"
    _git(repo, "worktree", "add", "-q", "-b", "hm/slug", str(wt))
    assert not (wt / ".claude").exists()
    monkeypatch.chdir(wt)

    cfg = soi.load_config(soi.resolve_base_root(Path.cwd()))

    assert cfg["antigravity"]["model"] == "Gemini 3.1 Pro (Low)"
    assert cfg["antigravity"]["model"] != soi.DEFAULT_ANTIGRAVITY_MODEL
    assert cfg["codex"]["hermetic"] is False


def test_config_defaults_when_no_harness_yaml_at_base(repo: Path) -> None:
    cfg = soi.load_config(repo)
    assert cfg["antigravity"]["model"] == soi.DEFAULT_ANTIGRAVITY_MODEL
    assert cfg["codex"]["hermetic"] is True


# ── golden argv ──────────────────────────────────────────────────────────────


def test_codex_golden_argv_hermetic(tmp_path: Path) -> None:
    schema = tmp_path / "s.json"
    out = tmp_path / "o.txt"
    assert soi.build_codex_argv(schema_path=schema, out_path=out, hermetic=True) == [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--ignore-user-config",
        "--ignore-rules",
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(out),
        "-",
    ]


def test_codex_golden_argv_non_hermetic(tmp_path: Path) -> None:
    schema = tmp_path / "s.json"
    out = tmp_path / "o.txt"
    assert soi.build_codex_argv(schema_path=schema, out_path=out, hermetic=False) == [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(out),
        "-",
    ]


def test_agy_golden_argv() -> None:
    # `--sandbox` BEFORE `--print`: `--print` takes the prompt as its VALUE, so the
    # shipped `agy --print --sandbox` made `--sandbox` the prompt and every vote
    # vacuous. Probed 2026-07-25: flags AFTER the value are still parsed.
    assert soi.build_agy_argv(prompt="P", model="Gemini 3.1 Pro (High)") == [
        "agy",
        "--sandbox",
        "--print",
        "P",
        "--print-timeout",
        "240s",
        "--model",
        "Gemini 3.1 Pro (High)",
    ]


# ── prompt delivery + payload channel (argv is blind to both) ────────────────


def test_codex_prompt_is_delivered_on_stdin_and_payload_read_from_out_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_schema(repo)
    calls: list[dict[str, Any]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        calls.append({"argv": argv, "kwargs": kwargs})
        # The invoker owns the out-file path; write the payload where codex would.
        Path(argv[argv.index("--output-last-message") + 1]).write_text(
            json.dumps(_valid_payload()), encoding="utf-8"
        )
        return _FakeCompleted(0)

    # Routed through `_run_with` like every other invoke-level test: a direct setattr
    # would silently require that an explicit `base_root` produces zero git shell-outs,
    # and an implementation that normalises it through `resolve_base_root` would fail
    # inside the fake with a ValueError naming neither the cause nor the contract.
    _run_with(monkeypatch, fake_run)
    result = soi.invoke(
        model="codex", prompt="PROMPT BODY", slug="s", stage="review", base_root=repo
    )

    assert result["status"] == "invoked"
    assert result["findings"][0]["summary"] == "a real finding"
    # An unwired stdin gives codex EOF → empty prompt → exit 0, empty payload, and a
    # perfectly correct argv. Pin the channel, not just the flags.
    assert calls[0]["kwargs"]["input"] == "PROMPT BODY"


def test_agy_prompt_is_an_argv_value_with_no_stdin_and_payload_from_stdout(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        calls.append({"argv": argv, "kwargs": kwargs})
        return _FakeCompleted(0, stdout=json.dumps(_valid_payload()))

    _run_with(monkeypatch, fake_run)
    result = soi.invoke(
        model="antigravity", prompt="PROMPT BODY", slug="s", stage="review", base_root=repo
    )

    assert result["status"] == "invoked"
    assert calls[0]["kwargs"].get("input") is None
    argv = calls[0]["argv"]
    delivered = argv[argv.index("--print") + 1]
    assert delivered.startswith("PROMPT BODY")
    # `startswith` alone is satisfied by an `invoke` that hands the RAW prompt to
    # `build_agy_argv`, skipping `truncate_prompt`. That is ADR-003's CR-1 failure in
    # full: Phase 3 deletes the partial's output-shape instruction, so a prompt without
    # the envelope leaves agy no shape signal at all, it answers in prose, and EVERY
    # ordinary antigravity call classifies `failed`. Pin the composition.
    assert soi.AGY_OUTPUT_CONTRACT in delivered


# ── schema resolution ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cwd_kind",
    ["base", "worktree"],
    ids=["base-cwd-control", "worktree-cwd-discriminating"],
)
def test_schema_path_on_the_constructed_argv_is_the_base_rooted_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch, cwd_kind: str
) -> None:
    # H1 itself, and `is_absolute() and exists()` does NOT cover it. A cwd-relative
    # implementation resolves to `wt/.claude/schemas/…`, finds it absent, and — per
    # ADR-001 — falls back to the packaged asset in a temp file, which is ALSO
    # absolute and ALSO exists. Both weak assertions hold in the broken world. Only
    # equality against the base-rooted file discriminates the two.
    expected = _write_schema(repo).resolve()
    wt = repo / ".worktrees" / "slug"
    _git(repo, "worktree", "add", "-q", "-b", "hm/slug", str(wt))
    assert not (wt / ".claude").exists()
    monkeypatch.chdir(repo if cwd_kind == "base" else wt)

    captured: list[list[str]] = []

    def fake(argv: list[str], **kw: Any) -> _FakeCompleted:
        captured.append(argv)
        Path(argv[argv.index("--output-last-message") + 1]).write_text(
            json.dumps(_valid_payload()), encoding="utf-8"
        )
        return _FakeCompleted(0)

    _run_with(monkeypatch, fake)
    soi.invoke(model="codex", prompt="p", slug="s", stage="review")

    argv = captured[0]
    sp = Path(argv[argv.index("--output-schema") + 1])
    assert sp.is_absolute()
    assert sp == expected


def test_missing_default_schema_falls_back_to_the_packaged_asset(repo: Path) -> None:
    # No `.claude/schemas/` anywhere — the shipped default must still produce a usable
    # schema rather than killing the call.
    p, ours = soi.resolve_schema_path(repo, soi.load_config(repo))
    assert p.is_absolute()
    assert p.exists()
    assert json.loads(p.read_text(encoding="utf-8"))["title"]
    # We materialised it, so we own the delete.
    assert ours is True


def test_missing_explicit_schema_is_a_skip_naming_the_path(repo: Path) -> None:
    # Silently substituting the default for a mis-configured explicit path would turn
    # a configuration error into a successful-looking vote against the wrong schema.
    cfg = soi.load_config(repo)
    cfg["codex"]["output_schema_path"] = ".claude/schemas/my-custom.json"

    with pytest.raises(soi.SecondOpinionSkipError) as exc:
        soi.resolve_schema_path(repo, cfg)
    assert "my-custom.json" in str(exc.value)


# ── truncation ───────────────────────────────────────────────────────────────


def test_under_budget_body_is_byte_identical_and_still_carries_the_contract() -> None:
    body = "x" * 90_000
    out = soi.truncate_prompt(body)
    assert body in out  # body untouched
    assert soi.AGY_OUTPUT_CONTRACT in out  # unconditional envelope
    assert soi.TRUNCATION_MARKER_PREFIX not in out
    assert len(out.encode("utf-8")) <= soi.PROMPT_LIMIT_BYTES


def test_over_budget_is_truncated_and_still_carries_contract_and_marker() -> None:
    body = "x" * 130_000
    out = soi.truncate_prompt(body)
    assert len(out.encode("utf-8")) <= soi.PROMPT_LIMIT_BYTES
    assert soi.AGY_OUTPUT_CONTRACT in out
    assert soi.TRUNCATION_MARKER_PREFIX in out
    assert "130000" in out  # original byte count named


def test_multibyte_body_is_measured_in_bytes_and_never_split_mid_character() -> None:
    # A 100 000-CHARACTER CJK body is ~300 000 bytes. Character-count truncation
    # passes an ASCII-only test and then fails execve with E2BIG.
    body = "가" * 60_000
    assert len(body) < soi.PROMPT_LIMIT_BYTES < len(body.encode("utf-8"))

    out = soi.truncate_prompt(body)

    assert len(out.encode("utf-8")) <= soi.PROMPT_LIMIT_BYTES
    # A bare `out.encode().decode()` round-trip cannot fail for any Python `str`, so it
    # would carry the "never split" half on a no-op. The implementation that splits —
    # `body.encode()[:BUDGET].decode("utf-8", errors="replace")` — is caught only by
    # looking for the replacement character it substitutes.
    assert "�" not in out
    assert soi.AGY_OUTPUT_CONTRACT in out


def test_output_contract_example_satisfies_the_validator() -> None:
    # The contract text INSTRUCTS the model; `validate_payload` JUDGES the reply. They
    # are a producer/consumer pair inside one process — the drift class this project
    # has recorded. If the example drifts out of the validator's accepted surface, agy
    # is told to emit a shape the invoker then rejects, and every vote is `failed`.
    #
    # Asserting `AGY_OUTPUT_CONTRACT in truncate_prompt(SMOKE_PROMPT)` would NOT catch
    # this: the envelope is unconditional, so that holds for any SMOKE_PROMPT at all,
    # including the empty string — invariant over the only variable it names.
    soi.validate_payload(json.loads(soi.AGY_OUTPUT_CONTRACT_EXAMPLE))
    assert soi.AGY_OUTPUT_CONTRACT_EXAMPLE in soi.AGY_OUTPUT_CONTRACT


def test_smoke_prompt_asks_for_a_finding_list() -> None:
    # `/hm:health`'s antigravity check is only a degradation detector if its prompt can
    # actually produce a validating payload.
    assert soi.SMOKE_PROMPT.strip()
    assert "findings" in soi.SMOKE_PROMPT.lower()


# ── validate_payload ─────────────────────────────────────────────────────────


def test_validate_payload_accepts_a_finding_without_evidence() -> None:
    # Deliberately laxer than `--output-schema`: agy has no CLI-level enforcement, so
    # requiring the full schema would turn every real agy reply into `failed` — the
    # same zero votes, with better telemetry.
    soi.validate_payload({"findings": [{"severity": "high", "message": "m"}]})


def test_minimal_finding_classifies_invoked_through_the_whole_pipeline(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The validator accepting a minimal finding proves nothing about the ADAPTER, which
    # runs next and direct-indexes `severity`. Drive the minimal shape end to end so the
    # laxness bullet is pinned where it is actually consumed, not one layer above it.
    payload = {"findings": [{"severity": "high", "message": "m"}]}
    _run_with(monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=json.dumps(payload)))

    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "invoked"
    assert r["findings"][0]["summary"] == "m"


def test_corrupt_base_config_is_skipped_not_invoked(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The narrow `skipped` arm of ADR-008's resolution wrapper. Without a test the
    # reason string is prose that no code path can reach — specified-but-unimplemented,
    # which is how the ledger acquires statuses nobody can produce.
    cfg = repo / ".claude" / "harness.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("second_opinion:\n  codex:\n    - [broken: {{\n", encoding="utf-8")
    _run_with(
        monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=json.dumps(_valid_payload()))
    )

    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "skipped"
    assert "config load failed" in r["reason"]
    assert "CLI not installed" not in r["reason"]


def test_validate_payload_normalises_severity_like_the_adapter() -> None:
    soi.validate_payload({"findings": [{"severity": " Critical ", "message": "m"}]})


def test_validate_payload_accepts_an_empty_findings_list() -> None:
    # A model that genuinely found nothing is a valid vote, not a failure.
    soi.validate_payload({"findings": []})


@pytest.mark.parametrize(
    "payload",
    [
        [{"severity": "high", "message": "m"}],
        {"answer": "I am a chatty model"},
        {"findings": [{"title": "t", "description": "d", "recommendation": "r"}]},
        {"findings": [{"message": "no severity"}]},
        {"findings": [{"severity": "high", "message": ""}]},
        {"findings": [{"severity": "blocker", "message": "m"}]},
    ],
    ids=["bare-list", "answer-dict", "agy-title-shape", "no-severity", "empty-message", "bad-enum"],
)
def test_validate_payload_rejects_unusable_shapes(payload: Any) -> None:
    # `agy-title-shape` is not hypothetical: it is what agy actually returned during
    # this task's planning, and the adapter accepted it into seven empty summaries.
    with pytest.raises(soi.PayloadInvalidError):
        soi.validate_payload(payload)


# ── status matrix (ADR-008, one test per branch) ─────────────────────────────


def test_branch1_missing_binary_is_skipped_not_installed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Under `shell=False` there is no exit 127 — a missing binary RAISES. The whole
    # graceful-degrade contract inherited 127 from a shell that is no longer there.
    def fake(argv: list[str], **kw: Any) -> _FakeCompleted:
        raise FileNotFoundError(2, "No such file or directory", argv[0])

    _run_with(monkeypatch, fake)
    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)
    assert r["status"] == "skipped"
    assert "not installed" in r["reason"]


def test_branch2_timeout_is_skipped_with_timeout_reason(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(argv: list[str], **kw: Any) -> _FakeCompleted:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=soi.AGY_TIMEOUT_S)

    _run_with(monkeypatch, fake)
    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)
    assert r["status"] == "skipped"
    assert "timeout" in r["reason"]
    assert "not installed" not in r["reason"]


def test_branch3_other_exception_is_skipped_carrying_the_type(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A present-but-not-executable binary raises PermissionError — a sibling of
    # FileNotFoundError, not a subclass. Without a terminal branch it is a traceback.
    def fake(argv: list[str], **kw: Any) -> _FakeCompleted:
        raise PermissionError(13, "Permission denied", argv[0])

    _run_with(monkeypatch, fake)
    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)
    assert r["status"] == "skipped"
    assert "PermissionError" in r["reason"]


def test_branch4_nonzero_exit_is_skipped_carrying_the_code(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run_with(monkeypatch, lambda argv, **kw: _FakeCompleted(3, stderr="boom"))
    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)
    assert r["status"] == "skipped"
    assert "exit 3" in r["reason"]


def test_branch5_agy_prose_reply_is_failed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The most common antigravity degrade. `extract_antigravity_payload` raises by
    # contract; unguarded it propagates and breaks the never-block guarantee.
    _run_with(monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout="Sure! Here's my take..."))
    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)
    assert r["status"] == "failed"
    assert "not installed" not in r["reason"]


def test_branch5_codex_empty_out_file_is_failed_not_missing_cli(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The out-file is mktemp-created so it EXISTS but may be empty. Widening branch 1
    # to cover the read would report "CLI not installed" — the most misleading string
    # in the table.
    _write_schema(repo)
    _run_with(monkeypatch, lambda argv, **kw: _FakeCompleted(0))
    r = soi.invoke(model="codex", prompt="p", slug="s", stage="review", base_root=repo)
    assert r["status"] == "failed"
    assert "not installed" not in r["reason"]


def test_branch7_valid_payload_is_invoked(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run_with(
        monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=json.dumps(_valid_payload()))
    )
    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)
    assert r["status"] == "invoked"
    assert r["reason"] is None


def test_out_of_vocabulary_severity_is_failed_not_raised(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `map_severity` raises and `adapt_*_finding` indexes `finding["severity"]`
    # directly. Adapting before validating turns a bad payload into a crash — this is
    # the only assertion that distinguishes the two pipeline orders.
    payload = {"findings": [{"severity": "blocker", "message": "m"}], "summary": "s"}
    _run_with(monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=json.dumps(payload)))
    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)
    assert r["status"] == "failed"


def test_missing_git_degrades_instead_of_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `resolve_base_root` shells out too, and that call sits OUTSIDE branches 1-3 as
    # first drafted — so a machine without `git` would raise straight out of `invoke`,
    # breaking the never-block contract in the module whose purpose is to hold it.
    # Patched directly (not via `_run_with`, which delegates git to the real binary).
    def no_git(argv: list[str], **kw: Any) -> _FakeCompleted:
        if argv and argv[0] == "git":
            raise FileNotFoundError(2, "No such file or directory", "git")
        return _FakeCompleted(0, stdout=json.dumps(_valid_payload()))

    monkeypatch.setattr(soi.subprocess, "run", no_git)
    monkeypatch.chdir(tmp_path)

    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review")

    # `status in {"invoked", "skipped"}` would be an or-disjunction satisfied by almost
    # any implementation. The design has a determinate answer here: the resolution
    # chain is porcelain → show-toplevel → cwd, so when both git calls fail the cwd
    # fallback still yields a usable root and the call proceeds normally.
    assert r["status"] == "invoked"
    assert (tmp_path / ".claude" / "observability" / "second-opinion.jsonl").exists()


def test_invoker_error_before_the_cli_call_still_returns_json(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `mkstemp` / `write_text` / `_packaged_schema` run BEFORE the branch-1..3 try. A
    # read-only or full TMPDIR made them raise straight out of `invoke()` — a traceback
    # instead of a JSON line, on a path the recipe tells the operator means "bad
    # arguments, not the model". The terminal guard is the "Never raises" contract.
    def boom(*a: Any, **kw: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(soi.tempfile, "mkstemp", boom)

    r = soi.invoke(model="codex", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "skipped"
    assert "invoker error" in r["reason"]
    assert "OSError" in r["reason"]


def test_temp_files_are_removed_on_every_branch(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # One leaked file per codex call, plus one more per call whenever the packaged
    # schema is materialised. Both hold review content and accumulate silently.
    before = set(Path(soi.tempfile.gettempdir()).glob("hm-so-*"))
    _run_with(monkeypatch, lambda argv, **kw: _FakeCompleted(0))  # empty out-file → failed

    r = soi.invoke(model="codex", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "failed"
    assert set(Path(soi.tempfile.gettempdir()).glob("hm-so-*")) == before


def test_failed_reason_carries_what_the_cli_actually_said(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Observed 2026-07-25: agy replied "no output produced — a tool required the
    # 'command' permission that headless mode cannot prompt for", and the operator
    # would have read only "ValueError". A degrade path that cannot distinguish causes
    # is the defect class this whole module exists to remove.
    cli_says = 'jetski: no output produced — a tool required the "command" permission'
    _run_with(monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=cli_says))

    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "failed"
    assert "command" in r["reason"]
    assert "permission" in r["reason"]


def test_schema_path_escaping_the_repo_is_skipped(repo: Path) -> None:
    # `models.py` rejects absolute paths and `..` segments — but that validator never
    # runs here, because `load_config` reads raw YAML.
    cfg = soi.load_config(repo)
    cfg["codex"]["output_schema_path"] = "../../etc/passwd.json"

    with pytest.raises(soi.SecondOpinionSkipError) as exc:
        soi.resolve_schema_path(repo, cfg)
    assert "escapes" in str(exc.value)


def test_unreadable_prompt_file_returns_json_not_a_traceback(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `main()` read the prompt file before `invoke()`, i.e. outside the contract.
    rc = soi.main(
        [
            "--model",
            "codex",
            "--prompt-file",
            str(repo / "does-not-exist.txt"),
            "--slug",
            "s",
            "--stage",
            "review",
        ]
    )

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "skipped"
    assert "prompt file unreadable" in out["reason"]


def test_truncate_budget_never_goes_negative() -> None:
    # `raw[:negative]` is a slice from the END — a small limit would return nearly the
    # whole body, blowing past the very limit it enforces.
    out = soi.truncate_prompt("x" * 5000, limit_bytes=100)
    assert len(out.encode("utf-8")) <= len(soi.AGY_OUTPUT_CONTRACT.encode("utf-8")) + 200
    assert "xxxx" not in out


# ── ledger ───────────────────────────────────────────────────────────────────


def _ledger_rows(base: Path) -> list[dict[str, Any]]:
    p = base / ".claude" / "observability" / "second-opinion.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_ledger_writes_exactly_one_row_under_the_base_root_from_a_worktree(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `codex_ledger.main()` roots at `Path.cwd()`. From a worktree that is a
    # gitignored directory `task-land` deletes — the calibration row evaporates.
    wt = repo / ".worktrees" / "slug"
    _git(repo, "worktree", "add", "-q", "-b", "hm/slug", str(wt))
    monkeypatch.chdir(wt)
    _run_with(
        monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=json.dumps(_valid_payload()))
    )

    soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)

    assert not (wt / ".claude" / "observability").exists()
    rows = _ledger_rows(repo)
    assert len(rows) == 1
    assert rows[0]["finding_ref"] == "n/a"
    assert rows[0]["disposition"] == "unresolved"
    assert rows[0]["status"] == "invoked"


def test_oversized_stderr_still_produces_a_written_row(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `skip_reason` is `max_length=500` under `strict=True`. An unbudgeted reason
    # raises ValidationError, the best-effort wrapper swallows it, and NO row is
    # written — for the branch whose whole purpose is telling the operator why.
    _run_with(monkeypatch, lambda argv, **kw: _FakeCompleted(3, stderr="E" * 5000))

    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "skipped"
    rows = _ledger_rows(repo)
    assert len(rows) == 1
    assert len(rows[0]["skip_reason"]) <= 400


def test_ledger_write_failure_does_not_change_the_returned_status(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **kw: Any) -> None:
        raise OSError("disk full")

    _run_with(
        monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=json.dumps(_valid_payload()))
    )
    monkeypatch.setattr(soi.codex_ledger, "emit", boom)

    r = soi.invoke(model="antigravity", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "invoked"
    # The setattr also pins a module-attribute import style (`from harness_maker import
    # codex_ledger`); under `from …codex_ledger import emit` it raises AttributeError
    # and the test errors loudly rather than passing. What the emptiness assertion
    # actually guards is a SECOND write path — an implementation that serialises or
    # appends the row somewhere other than through `emit` would leave a row behind
    # while the status assertion stayed green.
    assert _ledger_rows(repo) == []


def test_health_stage_row_is_accepted_by_model_and_shipped_schema(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The Python `Literal` and the shipped JSON enum are one contract in two files;
    # the existing parity test compares property NAMES only, so it is invariant over
    # exactly this change.
    _run_with(
        monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=json.dumps(_valid_payload()))
    )
    soi.invoke(model="antigravity", prompt="p", slug="health-smoke", stage="health", base_root=repo)

    rows = _ledger_rows(repo)
    assert len(rows) == 1
    assert rows[0]["stage"] == "health"

    schema_path = (
        Path(soi.__file__).parent / "templates" / "schemas" / "second-opinion-ledger.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "health" in schema["properties"]["stage"]["enum"]


# ── end-to-end through main() ────────────────────────────────────────────────


def test_main_from_worktree_cwd_with_no_root_resolves_against_base(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Every other test here is function-level. An argparse `default="."` on `--root`
    # would make "explicit wins" true of every invocation and reinstate H1 in full,
    # while all of them still passed.
    _write_schema(repo)
    _write_harness_yaml(repo, antigravity_model="Gemini 3.1 Pro (Low)", hermetic=True)
    wt = repo / ".worktrees" / "slug"
    _git(repo, "worktree", "add", "-q", "-b", "hm/slug", str(wt))
    prompt_file = wt / "p.txt"
    prompt_file.write_text("PROMPT", encoding="utf-8")
    monkeypatch.chdir(wt)

    seen: list[list[str]] = []

    def fake(argv: list[str], **kw: Any) -> _FakeCompleted:
        seen.append(argv)
        return _FakeCompleted(0, stdout=json.dumps(_valid_payload()))

    _run_with(monkeypatch, fake)

    rc = soi.main(
        [
            "--model",
            "antigravity",
            "--prompt-file",
            str(prompt_file),
            "--slug",
            "s",
            "--stage",
            "review",
        ]
    )

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "invoked"
    # The configured model came from the BASE harness.yaml, not from defaults.
    assert seen[0][seen[0].index("--model") + 1] == "Gemini 3.1 Pro (Low)"
    assert _ledger_rows(repo)


def test_main_requires_a_prompt_source(repo: Path) -> None:
    with pytest.raises(SystemExit):
        soi.main(["--model", "codex", "--slug", "s", "--stage", "review"])


def test_main_smoke_needs_no_prompt_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    _run_with(
        monkeypatch, lambda argv, **kw: _FakeCompleted(0, stdout=json.dumps(_valid_payload()))
    )

    rc = soi.main(
        ["--model", "antigravity", "--smoke", "--slug", "health-smoke", "--stage", "health"]
    )

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["status"] == "invoked"


def test_main_exits_zero_on_graceful_degrade(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The stage relays the JSON; a non-zero exit would leave it nothing to fold in at
    # exactly the moment the never-block contract exists for.
    monkeypatch.chdir(repo)

    def fake(argv: list[str], **kw: Any) -> _FakeCompleted:
        raise FileNotFoundError(2, "No such file or directory", argv[0])

    _run_with(monkeypatch, fake)
    rc = soi.main(["--model", "antigravity", "--smoke", "--slug", "s", "--stage", "review"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["status"] == "skipped"


# ── command-surface registration ─────────────────────────────────────────────


def test_module_is_registered_as_flagonly() -> None:
    # `test_command_surface_gate` fails any rendered `python -m harness_maker.<mod>`
    # whose module is absent from the registry; Phase 3's templates invoke this one.
    from harness_maker import command_registry

    spec = command_registry.MODULES["second_opinion_invoke"]
    assert spec.shape == "flagonly"
    assert not spec.guarded


# ── ownership + bounded read (REVIEW-2026-07-25 F3 / F4) ─────────────────────


def test_an_existing_user_schema_is_not_ours_to_delete(repo: Path) -> None:
    """F3: the flag is the delete permission, and it must be False for a file we found."""
    _write_schema(repo)
    p, ours = soi.resolve_schema_path(repo, soi.load_config(repo))
    assert p == (repo / ".claude" / "schemas" / "second-opinion-finding.schema.json").resolve()
    assert ours is False


def test_a_user_schema_living_in_the_temp_dir_survives_the_call(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3: ownership used to be INFERRED from location.

    `schema_path.parent == gettempdir()` is a guess at "is this mine to delete?", and
    the guess answers YES about a file the USER wrote whenever the repo sits under
    $TMPDIR. Here `gettempdir()` is pointed at the schema's own directory, which makes
    the retired predicate true; the file must still survive, because ownership is now
    recorded at creation rather than re-derived from where the file happens to live.
    """
    schema = _write_schema(repo)
    monkeypatch.setattr(soi.tempfile, "tempdir", str(schema.parent))

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        Path(argv[argv.index("--output-last-message") + 1]).write_text(
            json.dumps(_valid_payload()), encoding="utf-8"
        )
        return _FakeCompleted(0)

    _run_with(monkeypatch, fake_run)
    r = soi.invoke(model="codex", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "invoked"
    assert schema.exists(), "cleanup deleted a user file it never created"


def test_oversized_codex_output_fails_closed_naming_the_cap(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F4: over-cap output must fail CLOSED, not be silently truncated.

    `status == "failed"` alone does not discriminate — the old silent truncation also
    ended in `failed`, via a JSON parse error that named nothing. The reason string is
    the assertion that separates the two.
    """
    _write_schema(repo)
    monkeypatch.setattr(soi.codex_adapter, "_MAX_ANTIGRAVITY_BYTES", 64)

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        Path(argv[argv.index("--output-last-message") + 1]).write_text(
            json.dumps(_valid_payload()), encoding="utf-8"
        )
        return _FakeCompleted(0)

    _run_with(monkeypatch, fake_run)
    r = soi.invoke(model="codex", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "failed"
    assert "exceeds cap" in (r["reason"] or ""), r["reason"]


def test_the_cap_counts_bytes_not_characters(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F4: `_MAX_ANTIGRAVITY_BYTES` is byte-named; the old slice counted characters.

    The payload below is comfortably under the cap in CHARACTERS and over it in UTF-8
    BYTES, so the retired `read_text()[:N]` slice let it through untouched and reported
    `invoked`. This is the only case that distinguishes the two units.
    """
    _write_schema(repo)
    monkeypatch.setattr(soi.codex_adapter, "_MAX_ANTIGRAVITY_BYTES", 400)

    payload = _valid_payload()
    payload["findings"][0]["message"] = "가" * 120  # 120 chars, 360 bytes
    blob = json.dumps(payload, ensure_ascii=False)
    assert len(blob) < 400 < len(blob.encode("utf-8")), "fixture no longer straddles the cap"

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        Path(argv[argv.index("--output-last-message") + 1]).write_text(blob, encoding="utf-8")
        return _FakeCompleted(0)

    _run_with(monkeypatch, fake_run)
    r = soi.invoke(model="codex", prompt="p", slug="s", stage="review", base_root=repo)

    assert r["status"] == "failed"
    assert "exceeds cap" in (r["reason"] or ""), r["reason"]
