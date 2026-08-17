"""Repo-wide test fixtures — the session-env pin, owned in ONE place.

`tests/unit/conftest.py` has pinned `CLAUDECODE` / `CLAUDE_ENV_FILE` / `HM_SESSION_ID`
since the 2026-06-21 fix for `[fail:design] runtime-env-gate-dead-on-arrival`. Every other
test directory inherited nothing, so `tests/integration/test_fresh_install_readiness.py`
read the developer's live Claude session and failed (Side 53 < 66, Production 46 < 72) when
run from inside one — while passing under `env -u CLAUDECODE`. A release procedure that
tells the operator to run a suite locally cannot have a suite whose colour depends on which
shell they used.

Lifting the pin here rather than copying it into four more conftests: unlike the
install-ref pin next door (four deliberate copies, because a shared helper's import is
rootdir-sensitive and a silently-unloaded pin is the failure IT prevents), this one needs
no import — pytest applies the rootdir conftest to every directory beneath it, and its
absence is loud rather than silent (`tests/integration/test_env_isolation.py` runs an inner
pytest with all three variables set and asserts the inner run is green).

Opt-out: mark a test `@pytest.mark.live_env` when it must observe the real environment.
Declaring the escape hatch here, once, is deliberate — an autouse fixture cannot be
overridden by a sibling fixture without one, so leaving it undefined means the first test
that needs the live env improvises a `setenv`-after-autouse that works only because of
fixture ordering nothing pins, and every later test copies that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SESSION_ENV_KEYS = ("CLAUDECODE", "CLAUDE_ENV_FILE", "HM_SESSION_ID")

#: The tests tree. `_redirect_ledger_writes` redirects a ledger append only when its target
#: would CONTAIN this directory — i.e. only when it resolved to this checkout, which is the
#: leak, and never when a test built its own repository under tmp_path.
_TESTS_ROOT = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _isolate_session_env(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the Claude-session variables unless the test asks for them.

    `CLAUDECODE` is the one that bites: `readiness._dim_guardrails` treats it as "we are
    inside a Claude Code session" and then emits a hard-gating signal, so an unpinned run
    under Claude Code floors the `guardrails` dimension to 0 and drags every composite
    assertion down with it.
    """
    if request.node.get_closest_marker("live_env") is not None:
        return
    for key in _SESSION_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _redirect_ledger_writes(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No test may append a row to the real repository's second-opinion ledger (AC-001).

    The leak is measured: on 2026-08-17 the live ledger held 150 rows written by the unit
    suite, and a naive per-model read reported codex at 64.9% loss where the truth was 1.3%.
    The shape is `second_opinion_invoke.main()`/`.invoke()` called with no `base_root` and no
    `chdir`, so base-root resolution walks up to the enclosing checkout.

    Prevention, not detection, and **autouse** — a per-test opt-in protects only the sites
    that remember to ask, which is the hand list a suite-wide invariant exists to avoid. A
    marker on the ROW cannot work at all: `codex_ledger.SecondOpinionRecord` is
    `extra="forbid"`.

    **This patches the WRITE, not base-root resolution.** An earlier version redirected
    `second_opinion_invoke.resolve_base_root`, and Phase D found two regressions no review
    round had predicted. (1) `mutation_receipt._base_root` calls that same resolver, at call
    time, to locate a COMMITTED ledger — so a structural gate began reading an empty sandbox.
    A general-purpose resolver has consumers beyond the thing being isolated. (2) A
    root-conftest import of `second_opinion_invoke` makes `test_dep_map` map every module in
    its transitive closure to the whole tests tree (its ADR-003 rule: an autouse fixture that
    breaks takes its directory with it), silently retiring targeted test selection.
    `codex_ledger`'s closure is 2 modules against 6, and redirecting the append is what the
    invariant is actually about.

    **Function-scoped**, because the canaries assert their sandbox holds exactly one row.

    **Its opt-out is its own marker**, not `live_env`. Reusing the env-pin marker made one
    decorator disable two orthogonal invariants: a test marked to observe the real
    `CLAUDECODE` also lost the ledger redirect, and the bypass scan sees patch calls and
    fixture shadowing, never markers. Four reviewer voices found it. `live_ledger` exists so
    that opting out of the ledger isolation has to be a decision about the ledger.
    """
    if request.node.get_closest_marker("live_ledger") is not None:
        return

    import harness_maker.codex_ledger as codex_ledger

    real_emit = codex_ledger.emit
    sandbox = tmp_path / "hm-ledger-sandbox"

    def _redirect(record: object, *, project_root: Path | None = None, **kw: object) -> Path:
        # Redirect a write that would land anywhere inside this checkout. A test that built
        # its own repository under tmp_path keeps its own root, which is what keeps the
        # deliberate-fixture case and the accidental-leak case distinguishable.
        #
        # **Resolve first.** `emit` resolves `project_root` itself, so an unresolved
        # comparison here decides on a different path than the one written to: a relative
        # root (`Path(".")` — which `invoke()`'s except branch really produces, per its own
        # comment about a concurrent `task-land`) or a symlinked root failed the test and
        # then resolved to this checkout. Six reviewer voices found that hole.
        #
        # **Both directions.** `_TESTS_ROOT.is_relative_to(t)` alone is ancestor-only, so a
        # root *inside* the checkout — `<repo>/src`, `<repo>/.worktrees/x` — was left alone
        # and wrote into the working tree.
        target = Path(project_root).resolve() if project_root is not None else None
        if (
            target is None
            or _TESTS_ROOT.is_relative_to(target)
            or target.is_relative_to(_TESTS_ROOT.parent)
        ):
            sandbox.mkdir(parents=True, exist_ok=True)
            target = sandbox
            # An ABSOLUTE `observability_dir` was legal against the caller's own root; with
            # the root substituted it now escapes `emit`'s containment guard and raises
            # inside an autouse fixture, which is a baffling place to debug. Drop it and let
            # the sandbox's default apply — the write is being redirected anyway.
            od = kw.get("observability_dir")
            if od is not None and Path(od).is_absolute():  # type: ignore[arg-type]
                kw["observability_dir"] = None
        return real_emit(record, project_root=target, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(codex_ledger, "emit", _redirect)
