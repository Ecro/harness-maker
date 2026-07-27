"""Phase 8 — A1 check-suite verification cache tests."""

from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from harness_maker.observability.verification_cache import (
    _ENV_ALLOW,
    _ENV_ALLOW_EXCEPTIONS,
    _ENV_ALLOW_PATTERNS,
    _env_hash,
    _is_hashed_env,
    compute_relevant_skip_key,
    compute_skip_key,
    is_fresh,
    is_relevant_path,
    main,
    mark_passed,
)


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    """Create a minimal git repo for skip-key computation."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
    (tmp_path / "uv.lock").write_text("# lock\n")

    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


def test_verification_key_includes_sha(fake_project: Path) -> None:
    """Key must change when HEAD sha changes."""
    key1 = compute_skip_key(fake_project)
    (fake_project / "new.txt").write_text("data")
    import subprocess

    subprocess.run(["git", "add", "."], cwd=fake_project, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=fake_project,
        capture_output=True,
        check=True,
    )
    key2 = compute_skip_key(fake_project)
    assert key1 != key2


def test_verification_key_includes_uv_lock(fake_project: Path) -> None:
    """Key must change when uv.lock changes."""
    key1 = compute_skip_key(fake_project)
    (fake_project / "uv.lock").write_text("# changed lock\n")
    key2 = compute_skip_key(fake_project)
    assert key1 != key2


def test_verification_key_includes_tool_versions(fake_project: Path) -> None:
    """Key must change when tool versions change (mocked)."""
    key1 = compute_skip_key(fake_project)
    with patch(
        "harness_maker.observability.verification_cache._tool_versions",
        return_value={"python": "3.99.0", "ruff": "99.0", "mypy": "99.0", "pytest": "99.0"},
    ):
        key2 = compute_skip_key(fake_project)
    assert key1 != key2


def test_verification_key_includes_project_root(tmp_path: Path) -> None:
    """Two projects with same content but different roots must have different keys."""
    import subprocess

    for name in ("repo_a", "repo_b"):
        d = tmp_path / name
        d.mkdir()
        (d / "pyproject.toml").write_text("[project]\nname='test'\n")
        (d / "uv.lock").write_text("# lock\n")
        subprocess.run(["git", "init"], cwd=d, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=d,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=d,
            capture_output=True,
            check=True,
        )
        subprocess.run(["git", "add", "."], cwd=d, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=d,
            capture_output=True,
            check=True,
        )

    key_a = compute_skip_key(tmp_path / "repo_a")
    key_b = compute_skip_key(tmp_path / "repo_b")
    assert key_a != key_b, "Different project roots must produce different keys"


def test_verification_key_invalidates_on_lang_change(fake_project: Path) -> None:
    """Changing LANG env var must invalidate the key (C1 validator concern)."""
    old_lang = os.environ.get("LANG")
    try:
        os.environ["LANG"] = "en_US.UTF-8"
        key1 = compute_skip_key(fake_project)
        os.environ["LANG"] = "C"
        key2 = compute_skip_key(fake_project)
        assert key1 != key2
    finally:
        if old_lang is None:
            os.environ.pop("LANG", None)
        else:
            os.environ["LANG"] = old_lang


def test_verification_key_invalidates_on_tz_change(fake_project: Path) -> None:
    """Changing TZ env var must invalidate the key."""
    old_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "UTC"
        key1 = compute_skip_key(fake_project)
        os.environ["TZ"] = "America/New_York"
        key2 = compute_skip_key(fake_project)
        assert key1 != key2
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz


def test_verification_key_ignores_pwd(fake_project: Path) -> None:
    """PWD must not affect the key — it is simply not allowlisted.

    (Was "PWD is in the ignore set"; the ignore set no longer exists.)
    """
    old_pwd = os.environ.get("PWD")
    try:
        os.environ["PWD"] = "/tmp/foo"
        key1 = compute_skip_key(fake_project)
        os.environ["PWD"] = "/tmp/bar"
        key2 = compute_skip_key(fake_project)
        assert key1 == key2
    finally:
        if old_pwd is None:
            os.environ.pop("PWD", None)
        else:
            os.environ["PWD"] = old_pwd


def test_verification_skip_hit_only_when_all_match(fake_project: Path, tmp_path: Path) -> None:
    """is_fresh returns marker only after mark_passed; different key returns None."""
    cache_dir = tmp_path / "cache"
    with patch.dict(os.environ, {"HARNESS_MAKER_CACHE_DIR": str(cache_dir)}):
        key = compute_skip_key(fake_project)

        assert is_fresh(key) is None

        mark_passed(key, project_root=str(fake_project))

        result = is_fresh(key)
        assert result is not None
        assert result["passed"] is True
        assert result["key"] == key

        assert is_fresh("totally-different-key") is None


def test_only_allowlisted_env_vars_are_hashed() -> None:
    """The policy is an ALLOWLIST: a var is hashed only when it can change a verdict.

    Replaces the former blocklist check. Under the old inverted policy every one of the
    `not` cases below WAS hashed, which is why the key differed between the main loop
    and a subagent and the cache was permanently cold.
    """
    for name in ("PATH", "VIRTUAL_ENV", "LANG", "LC_ALL", "TZ", "HOME", "INTEGRATION"):
        assert _is_hashed_env(name), f"{name} can change a verdict and must be hashed"
    for name in (
        "SSH_AUTH_SOCK",
        "WSL_DISTRO_NAME",
        "WT_SESSION",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_EFFORT",
        "AI_AGENT",
        "CODEX_COMPANION_SESSION_ID",
        "DISCORD_BOT_TOKEN",
        "ZEPHYR_BASE",
    ):
        assert not _is_hashed_env(name), f"{name} cannot change a verdict"


def test_relevant_key_ignores_work_docs_and_memory(fake_project: Path) -> None:
    key1 = compute_relevant_skip_key(fake_project)
    (fake_project / "work-docs").mkdir()
    (fake_project / "work-docs" / "PLAN-x.md").write_text("status: complete\n")
    (fake_project / ".claude" / "memory").mkdir(parents=True)
    (fake_project / ".claude" / "memory" / "session.md").write_text("note\n")
    key2 = compute_relevant_skip_key(fake_project)
    assert key1 == key2


def test_relevant_key_invalidates_on_source_change(fake_project: Path) -> None:
    key1 = compute_relevant_skip_key(fake_project)
    (fake_project / "src").mkdir()
    (fake_project / "src" / "pkg.py").write_text("VALUE = 1\n")
    key2 = compute_relevant_skip_key(fake_project)
    assert key1 != key2


def test_relevant_path_docs_behavior_opt_in() -> None:
    assert not is_relevant_path("CHANGELOG.md")
    assert is_relevant_path("CHANGELOG.md", docs_are_behavior=True)
    assert is_relevant_path("src/harness_maker/cli.py")
    assert not is_relevant_path(".claude/memory/session/2026-05-25.md")


def test_verification_cache_cli_check_and_mark(fake_project: Path, tmp_path: Path) -> None:
    cache_dir = tmp_path.parent / "verification-cache"
    with patch.dict(os.environ, {"HARNESS_MAKER_CACHE_DIR": str(cache_dir)}):
        assert main(["check", "--root", str(fake_project)]) == 1
        assert main(["mark-pass", "--root", str(fake_project), "--checks", "lint,pytest"]) == 0
        assert main(["check", "--root", str(fake_project)]) == 0


# --- launcher-volatile env values (fail:design verification-cache-key-nondeterministic) ---

_EPH = "/home/u/.cache/uv/builds-v0/.tmp"


def _key_with(project: Path, **over: str) -> str:
    """compute_relevant_skip_key under a patched environment."""
    with patch.dict(os.environ, over, clear=False):
        return compute_relevant_skip_key(project)


def test_key_is_stable_across_ephemeral_launcher_envs(fake_project: Path) -> None:
    """The defect: every rendered harness command runs via `uv run --with <pkg>`, which
    builds a throwaway env per invocation under `~/.cache/uv/builds-v*/.tmpXXXXXX` and
    exports it through PATH and VIRTUAL_ENV. Hashing those verbatim made the key change
    on every call, so no marker could ever be fresh and `/hm:verify` + `/hm:wrapup` each
    re-ran the full suite forever — indistinguishable from correct invalidation.
    """
    keys = {
        _key_with(
            fake_project,
            PATH=f"{_EPH}{tag}/bin:/usr/bin:/bin",
            VIRTUAL_ENV=f"{_EPH}{tag}",
        )
        for tag in ("AAAAAA", "BBBBBB", "CCCCCC")
    }
    assert len(keys) == 1, f"key still churns per invocation: {keys}"


def test_a_real_path_change_still_invalidates(fake_project: Path) -> None:
    """Scrubbing is value-level, not variable-level: PATH stays in the hash.

    Ignoring PATH outright would have fixed the churn too, and would have been wrong —
    PATH is allowlisted precisely because a real toolchain move must invalidate, so the
    scrub has to target the volatile SUBSTRING rather than drop the variable.
    (Was justified by "over-invalidate rather than risk a false PASS"; that policy was
    retired on 2026-07-27 and no longer holds.)
    """
    base = _key_with(fake_project, PATH=f"{_EPH}A/bin:/usr/bin", VIRTUAL_ENV=f"{_EPH}A")
    moved = _key_with(fake_project, PATH=f"{_EPH}A/bin:/opt/other/bin", VIRTUAL_ENV=f"{_EPH}A")
    assert base != moved


def test_a_test_gating_env_var_still_invalidates(fake_project: Path) -> None:
    """`INTEGRATION=1` genuinely changes which tests run, so it must invalidate.

    Renamed from `test_an_unknown_new_env_var_still_invalidates`. The assertion is
    unchanged and still passes, but its old docstring justified the inverted policy by
    claiming "no allowlist would have been guaranteed to name it" — `INTEGRATION` is
    named explicitly in `_ENV_ALLOW`, so that sentence was false the moment the policy
    flipped. Leaving it would be the sibling-field drift this repo keeps hitting: the
    executable half updated, the prose half still asserting the retired contract.
    """
    base = _key_with(fake_project, PATH=f"{_EPH}A/bin:/usr/bin")
    flagged = _key_with(fake_project, PATH=f"{_EPH}A/bin:/usr/bin", INTEGRATION="1")
    assert base != flagged


# ---------------------------------------------------- allowlist policy (this change)


def test_agent_identity_vars_do_not_change_the_key() -> None:
    """The measured defect: the main loop exports `CLAUDE_EFFORT`, a subagent does not.

    Measured 2026-07-27 before the fix — main loop hashed 43 vars, a subagent 42, and
    the single difference was `CLAUDE_EFFORT`. Every marker written by one context was
    therefore invisible to the other, so `/hm:verify` wrote a marker `/hm:wrapup` could
    never read and both re-ran the full suite. A permanently-cold cache is
    indistinguishable from a correctly-invalidated one, which is why this survived.

    Rejects an implementation that ignores only the exact vars named in the bug report:
    `AI_AGENT` / `CLAUDE_PID` / `CODEX_COMPANION_SESSION_ID` were IDENTICAL across the
    two contexts and were never the cause, so a fix targeting them would leave the
    actual defect live.

    Every value below is a SENTINEL, deliberately unlike anything the ambient
    environment holds. `_key_with` patches with `clear=False`, so asserting with the
    real ambient value (`CLAUDE_EFFORT="high"` on this machine) would set the var to
    what it already is, leave the key untouched, and pass against the very
    implementation this test exists to reject.
    """
    with patch.dict(os.environ, {}, clear=False):
        base = _env_hash()
    for var in (
        "CLAUDE_EFFORT",
        "AI_AGENT",
        "CLAUDE_PID",
        "CLAUDECODE",
        "CLAUDE_PLUGIN_DATA",
        "CLAUDE_TELEMETRY",
        "CODEX_COMPANION_SESSION_ID",
        "DBUS_SESSION_BUS_ADDRESS",
    ):
        sentinel = f"__hm_sentinel_{var.lower()}__"
        with patch.dict(os.environ, {var: sentinel}, clear=False):
            mutated = _env_hash()
        assert mutated == base, f"{var} is agent-identity metadata and must not move the key"


def test_unrelated_secrets_and_toolchains_do_not_change_the_key() -> None:
    """Rotating a Slack webhook must not invalidate the Python test cache.

    All eight were in the hashed set under the inverted policy, measured on this machine.
    Beyond the churn, hashing credentials at all is gratuitous.

    Sentinel values, for the same `clear=False` reason as the test above.
    """
    with patch.dict(os.environ, {}, clear=False):
        base = _env_hash()
    for var in (
        "DISCORD_BOT_TOKEN",
        "JENKINS_TOKEN",
        "JENKINS_USER",
        "PIPELINE_SLACK_WEBHOOK_URL",
        "ZEPHYR_BASE",
        "ZEPHYR_SDK_INSTALL_DIR",
        "NVM_DIR",
        "PULSE_SERVER",
    ):
        sentinel = f"__hm_sentinel_{var.lower()}__"
        with patch.dict(os.environ, {var: sentinel}, clear=False):
            mutated = _env_hash()
        assert mutated == base, f"{var} cannot affect whether lint/type/test pass"


# Written out as an INDEPENDENT literal, deliberately NOT derived from `_ENV_ALLOW`.
# Deriving it would delete a member's test case at the same moment it deleted the
# member — the fence would be invariant over the exact dimension it guards, which is
# this repo's most-recurring failure (`[fail:test] assertion-invariant-over-named-dimension`).
# `test_the_fence_covers_every_allowlist_member` closes the other direction.
_FENCE_VARS: tuple[str, ...] = (
    # _ENV_ALLOW literals
    "PATH",
    "VIRTUAL_ENV",
    "HOME",
    "TMPDIR",
    "TZ",
    "LANG",
    "SOURCE_DATE_EPOCH",
    "CI",
    "INTEGRATION",
    "HYPOTHESIS_PROFILE",
    "HM_RUN_PARALLEL_SESSION",
    "HM_MAIN_CHECKOUT_PATH",
    "INSTALL_CMD_TEST",
    "HARNESS_MAKER_FREEZE",
    # one representative per _ENV_ALLOW_PATTERNS entry
    "LC_ALL",
    "PYTHONHASHSEED",
    "UV_PYTHON_PREFERENCE",
    "RUFF_CACHE_DIR",
    "MYPY_CACHE_DIR",
    "PYTEST_ADDOPTS",
    "HYPOTHESIS_DATABASE",
    # additional PYTHON* members whose omission was a real stale-PASS hole before the
    # family became a pattern (review P1): user-site shadowing and text decoding both
    # change what pytest/mypy conclude.
    "PYTHONNOUSERSITE",
    "PYTHONUSERBASE",
    "PYTHONUTF8",
    "PYTHONIOENCODING",
)


def test_the_fence_covers_every_allowlist_member_pattern_and_exception() -> None:
    """A new allow entry with no fence case is an ungated member.

    The per-member fence below catches SHRINKAGE. This catches GROWTH-without-coverage
    in all THREE containers — an earlier draft checked `_ENV_ALLOW` only, so a new
    pattern or a new churn carve-out could be added with nothing exercising it (review
    P2). It is also how the first draft silently omitted `TMPDIR`,
    `PYTHONDONTWRITEBYTECODE` and `PYTHONWARNINGS` while claiming "one case per member".
    """
    fence = set(_FENCE_VARS)

    uncovered = _ENV_ALLOW - fence
    assert not uncovered, f"allowlist members with no fence case: {sorted(uncovered)}"

    unrepresented = [
        pat for pat in _ENV_ALLOW_PATTERNS if not any(fnmatch.fnmatch(v, pat) for v in fence)
    ]
    assert not unrepresented, f"allow patterns with no fence representative: {unrepresented}"

    # A carve-out must be exercised by the test that proves it is surgical, otherwise a
    # future addition silently widens the churn surface.
    assert set(_CARVE_OUT_VARS) >= _ENV_ALLOW_EXCEPTIONS, (
        f"carve-outs with no dedicated case: {sorted(_ENV_ALLOW_EXCEPTIONS - set(_CARVE_OUT_VARS))}"
    )


@pytest.mark.parametrize("var", _FENCE_VARS)
def test_every_build_affecting_var_still_invalidates(var: str) -> None:
    """The safety fence for the allowlist — one case per member that must stay in it.

    An allowlist's failure mode is silent SHRINKAGE: drop a name and the cache starts
    returning stale PASSes with no signal.

    Measured coverage, one deletion at a time, rather than asserted: every member of
    `_ENV_ALLOW`, of `_ENV_ALLOW_PATTERNS` and of `_ENV_ALLOW_EXCEPTIONS`, deleted on
    its own, fails at least one case here. There are no exempt members — an earlier
    draft had one (`HYPOTHESIS_PROFILE`, covered by both a literal and the
    `HYPOTHESIS_*` pattern, so neither deletion alone changed behaviour); the redundant
    literal was dropped rather than documented, because a contract with no exceptions
    is much harder to erode than one with a footnote.

    Asserts on `_env_hash()` — the component the allowlist actually governs — NOT on
    the composite `compute_relevant_skip_key`. The first draft of this test used the
    composite key and was WORTHLESS: `_tool_versions` shells out to
    `python3/ruff/mypy/pytest --version` with the patched environment inherited, so a
    sentinel value moved the key through tool resolution rather than through the env
    hash. Measured against the 17-case draft that existed at the time: removing `PATH` from
    `_ENV_ALLOW` left all of them green (the
    sentinel PATH stops resolving the tools), and removing `PYTHONHASHSEED` did too
    (the sentinel is not an integer, so `python3` refuses to start and its version
    comes back empty). The fence passed while gating nothing.

    This does NOT protect against OMISSION — a build-affecting variable nobody thought
    of is not covered by any test, and that is the accepted, documented cost of the
    policy flip. See the module docstring.

    Sentinel values so a case cannot pass by coincidentally matching whatever the
    ambient environment already holds — `patch.dict` runs with `clear=False`.
    `_scrub_volatile` only rewrites `/tmp/...`-style launcher paths, and no sentinel
    below is one, so none is scrubbed away before hashing.
    """
    sentinel = f"__hm_sentinel_{var.lower()}__"
    with patch.dict(os.environ, {}, clear=False):
        base = _env_hash()
    with patch.dict(os.environ, {var: sentinel}, clear=False):
        mutated = _env_hash()
    assert mutated != base


def test_a_path_change_reaches_the_composite_key_too(fake_project: Path) -> None:
    """End-to-end companion to the `_env_hash`-level fence above.

    Kept separate and deliberately narrow: it proves the env component actually reaches
    `compute_relevant_skip_key`, without pretending to gate allowlist membership (which
    the composite key cannot do — see the docstring above).
    """
    base = _key_with(fake_project, PATH="/usr/bin")
    assert _key_with(fake_project, PATH="/usr/bin:/opt/extra/bin") != base


# Every member of `_ENV_ALLOW_EXCEPTIONS` must appear here — asserted by
# `test_the_fence_covers_every_allowlist_member_pattern_and_exception`.
_CARVE_OUT_VARS: tuple[str, ...] = (
    "UV_RUN_RECURSION_DEPTH",
    "PYTEST_CURRENT_TEST",
    "PYTEST_XDIST_WORKER",
)


@pytest.mark.parametrize("var", _CARVE_OUT_VARS)
def test_per_invocation_bookkeeping_is_carved_out_of_its_pattern(var: str) -> None:
    """These match an allow PATTERN but are rewritten per invocation, not configured.

    `UV_RUN_RECURSION_DEPTH` increments on every nested `uv run` and every rendered
    harness command is invoked that way; pytest rewrites `PYTEST_CURRENT_TEST` per test
    function and `PYTEST_XDIST_WORKER` per worker. Admitting any of them re-introduces
    the per-invocation churn this whole change exists to remove.
    """
    with patch.dict(os.environ, {}, clear=False):
        base = _env_hash()
    with patch.dict(os.environ, {var: "__hm_sentinel_carveout__"}, clear=False):
        assert _env_hash() == base, f"{var} is per-invocation bookkeeping, not config"


def test_the_carve_outs_are_surgical_not_a_blanket_pattern_exclusion() -> None:
    """Sibling of the test above: the patterns those carve-outs sit in still bite.

    Without this, excluding the whole `UV_*` / `PYTEST_*` pattern would pass every
    carve-out case while silently dropping real configuration from the key.
    """
    with patch.dict(os.environ, {}, clear=False):
        base = _env_hash()
    for var in ("UV_PYTHON_PREFERENCE", "PYTEST_ADDOPTS"):
        with patch.dict(os.environ, {var: f"__hm_sentinel_{var.lower()}__"}, clear=False):
            assert _env_hash() != base, f"{var} is real configuration and must be hashed"


def test_the_key_is_identical_across_two_subprocess_invocations(fake_project: Path) -> None:
    """The detection idea recorded with `[fail:design] verification-cache-key-nondeterministic`.

    That entry named this test a year of hindsight ago — "a test asserting the key is
    stable across two subprocess invocations" — and it was never written, so instance 2
    of the same root-cause class shipped. Real subprocesses, real `os.environ`, so it
    catches an env leak no in-process monkeypatch would model.
    """
    code = (
        "import sys;from pathlib import Path;"
        "from harness_maker.observability.verification_cache import compute_skip_key;"
        "print(compute_skip_key(Path(sys.argv[1])))"
    )
    main_loop_env = {**os.environ, "CLAUDE_EFFORT": "high", "AI_AGENT": "main"}
    subagent_env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}
    subagent_env["AI_AGENT"] = "subagent"

    outs = []
    for env in (main_loop_env, subagent_env):
        proc = subprocess.run(
            [sys.executable, "-c", code, str(fake_project)],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        outs.append(proc.stdout.strip())

    assert outs[0] == outs[1], f"key differs between agent contexts: {outs}"


def test_the_uv_archive_path_is_not_scrubbed(fake_project: Path) -> None:
    """`archive-v*` encodes the identity of the installed package — real signal, unlike
    `builds-v*`, which is recreated per invocation. Scrubbing both would silently stop
    detecting a dependency swap."""
    a = _key_with(fake_project, PATH="/home/u/.cache/uv/archive-v0/AAA/bin:/usr/bin")
    b = _key_with(fake_project, PATH="/home/u/.cache/uv/archive-v0/BBB/bin:/usr/bin")
    assert a != b
