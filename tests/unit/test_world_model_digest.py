"""SPEC-world-model-followups: `hm world_model digest` (AC-001..006, AC-009).

Production symbols are resolved at call time so each test goes RED for its own reason.
The task fixtures are real git repos with real `hm/<slug>` worktrees, real SPEC approvals
(`spec_machine approve`) and a real verification marker — the digest's signals are read
from the same artifacts the stages write, not from stubs.
"""

from __future__ import annotations

import importlib
import io
import json
import subprocess
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker.spec_machine import load_golden_table

_REPO = Path(__file__).resolve().parents[2]
_SPEC_YAML = _REPO / "specs/SPEC-world-model-followups.machine.yaml"
_T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def _digest_mod() -> ModuleType:
    return importlib.import_module("harness_maker.world_model_digest")


def _run_cli(*argv: str) -> tuple[int, str]:
    wm = importlib.import_module("harness_maker.world_model")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = wm.main(list(argv))
    return int(rc or 0), buf.getvalue()


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=30
    )
    return proc.stdout


def _base(tmp: Path) -> Path:
    base = tmp / "base"
    base.mkdir(parents=True)
    _git(base, "init", "-q")
    _git(base, "config", "user.name", "t")
    _git(base, "config", "user.email", "t@t")
    _git(base, "commit", "-q", "--allow-empty", "-m", "init")
    return base


def _task(base: Path, slug: str) -> Path:
    wt = base / ".worktrees" / slug
    _git(base, "worktree", "add", "-q", "-b", f"hm/{slug}", str(wt))
    return wt


def _span(
    base: Path, slug: str, event: str, stage: str, session: str | None, minutes: int = 0
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event": event,
        "stage": stage,
        "cwd": str(base),
        "base_root": str(base),
        "git_branch": f"hm/{slug}",
        "task_slug": slug,
        "ts": (_T0 + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z"),
        "session_id": session,
    }


def _write_spans(base: Path, rows: list[dict[str, Any] | str]) -> None:
    ledger = base / ".claude/observability/stage-spans.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lines = [r if isinstance(r, str) else json.dumps(r) for r in rows]
    ledger.write_text(
        "\n".join(lines) + ("\n" if lines and not isinstance(rows[-1], str) else ""),
        encoding="utf-8",
    )


_SPEC_MD = """---
type: spec
task_slug: {slug}
status: approved
tier: 3
test_framework: pytest
---
# SPEC
### S1: x
**Given** a **When** b **Then** c
### AC-001: demo works
| Scenario | Verification mode | Test |
|---|---|---|
| S1 | unit | `test_x` |
"""

_SPEC_YAML_TMPL = """schema_version: 3
spec_slug: {slug}
irreversible_decisions: {irr}
parent_spec: null
verification_tier: 3
mutation_threshold: null
mutation_threshold_rationale: n/a
last_mutation_run: null
paths_to_mutate: []
spec_quality_score: null
spec_quality_score_at: null
ac:
- id: AC-001
  title: demo works
  type: mechanical
  test_ids: []
  executable_predicate: f(x) == 1
  golden_table: []
  rubric_id: null
  pending_test: true
  oracle_source: golden
  oracle_evidence: fixed by hand
  oracle_independence_waiver: null
"""

_IRR = (
    "\n- id: IRR-001\n  decision: d\n  category: public API/CLI contract"
    "\n  rationale: r\n  source: spec"
)


def _make_artifacts(wt: Path, slug: str, artifacts: list[str], cache: Path) -> None:
    from harness_maker import spec_machine
    from harness_maker.observability import verification_cache

    docs = wt / "work-docs"
    docs.mkdir(exist_ok=True)
    specs = wt / "specs"
    for a in artifacts:
        if a == "research":
            (docs / f"RESEARCH-{slug}.md").write_text(
                "---\ntype: research\n---\n", encoding="utf-8"
            )
        elif a == "plan":
            (docs / f"PLAN-{slug}.md").write_text("---\ntype: plan\n---\n", encoding="utf-8")
        elif a.startswith("spec_"):
            specs.mkdir(exist_ok=True)
            (specs / f"SPEC-{slug}.md").write_text(_SPEC_MD.format(slug=slug), encoding="utf-8")
            irr = _IRR if a == "spec_approved" else "[]"
            y = specs / f"SPEC-{slug}.machine.yaml"
            y.write_text(_SPEC_YAML_TMPL.format(slug=slug, irr=irr), encoding="utf-8")
            if a in ("spec_approved", "spec_exempt"):
                flags = ["--exempt"] if a == "spec_exempt" else []
                with redirect_stdout(io.StringIO()):
                    rc = spec_machine.main(["approve", "--yaml", str(y), *flags])
                assert rc == 0
        elif a.startswith("review_"):
            status = {
                "review_in_progress": "in-progress",
                "review_changes_requested": "CHANGES_REQUESTED",
                "review_approved": "APPROVED",
            }[a]
            (docs / f"REVIEW-{slug}-2026-10-02.md").write_text(
                f"---\ntype: review\ntask_slug: {slug}\nstatus: {status}\n---\n", encoding="utf-8"
            )
        elif a == "verify_marker":
            pass  # written last, after every other artifact, so the tree key is final
        else:
            raise AssertionError(a)
    if "verify_marker" in artifacts:
        with redirect_stdout(io.StringIO()):
            rc = verification_cache.main(
                ["mark-pass", "--root", str(wt), "--mode", "relevant", "--checks", "pytest"]
            )
        assert rc == 0


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    c = tmp_path / "cache"
    monkeypatch.setenv("HARNESS_MAKER_CACHE_DIR", str(c))
    return c


def _task_entry(d: dict[str, Any], slug: str) -> dict[str, Any]:
    return next(t for t in d["tasks"] if t["slug"] == slug)


# ---------------------------------------------------------------------------
# AC-001 — digest output never exceeds 1500 bytes (property)
# ---------------------------------------------------------------------------

_SUBJECT = st.text(
    alphabet=st.sampled_from(list("abc 가나다라마바사🚀✨-:()")), min_size=0, max_size=200
)


@settings(max_examples=60, derandomize=True, deadline=None)
@given(
    slugs=st.lists(st.from_regex(r"[a-z][a-z0-9-]{0,63}", fullmatch=True), max_size=20),
    subjects=st.lists(_SUBJECT, max_size=5),
    intent_ids=st.lists(st.from_regex(r"[A-Z][A-Z0-9-]{0,79}", fullmatch=True), max_size=20),
)
def test_ac001_digest_size_bound(
    slugs: list[str], subjects: list[str], intent_ids: list[str]
) -> None:
    payload = {
        "tasks": [
            {
                "slug": s,
                "next_stage": "execute",
                "last_stage": "execute",
                "last_seen": "2026-10-01T09:00:00Z",
                "other_session": None,
            }
            for s in slugs
        ],
        "more": 0,
        "autopilot": {"active": True, "level": "auto_safe", "pipeline": ["research", "spec"]},
        "intents": {
            "counts": {
                "conflicts": len(intent_ids),
                "fired_revisits": 0,
                "needs_revalidation": 0,
                "stale_evidence": 0,
            },
            "items": intent_ids,
        },
        "recent": subjects,
    }
    out = _digest_mod().render(payload)
    assert len(out.encode("utf-8")) <= 1500
    assert isinstance(json.loads(out), dict)


def test_ac001_real_digest_with_long_unicode_subjects_fits(tmp_path: Path, cache: Path) -> None:
    base = _base(tmp_path)
    for i in range(3):
        _git(
            base,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "가나다라마바사아자차카타파하🚀" * 10 + str(i),
        )
    for i in range(7):
        _task(base, f"task-with-a-fairly-long-slug-number-{i}")
    rc, out = _run_cli("digest", "--root", str(base))
    assert rc == 0
    assert len(out.strip().encode("utf-8")) <= 1500
    assert isinstance(json.loads(out), dict)


# ---------------------------------------------------------------------------
# AC-002 — digest always exits 0 with one valid JSON object (property)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def shared_base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = _base(tmp_path_factory.mktemp("ac002"))
    _task(base, "demo")
    return base


@settings(
    max_examples=40,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    garbage=st.one_of(
        st.binary(max_size=400),
        st.sampled_from(
            [
                b'{"event": "end", "stage": "", "task_slug": "demo"}\n',
                b'{"schema_version": 1, "event": "start", "stage": "hm:bogus",'
                b' "task_slug": "demo"}\n',
                b"{not json\n",
                b'{"task_slug": "demo"',
            ]
        ),
    )
)
def test_ac002_digest_never_fails(shared_base: Path, garbage: bytes) -> None:
    ledger = shared_base / ".claude/observability/stage-spans.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_bytes(garbage)
    rc, out = _run_cli("digest", "--root", str(shared_base))
    assert rc == 0
    assert isinstance(json.loads(out), dict)


def test_ac002_outside_git_reports_unavailable(tmp_path: Path) -> None:
    rc, out = _run_cli("digest", "--root", str(tmp_path))
    assert rc == 0
    assert "unavailable" in json.loads(out)


# ---------------------------------------------------------------------------
# AC-003 — next stage is derived from artifacts (golden)
# ---------------------------------------------------------------------------

_AC003 = load_golden_table(_SPEC_YAML, "AC-003")


@pytest.mark.parametrize("row", _AC003, ids=[f"r{i}" for i in range(len(_AC003))])
def test_ac003_next_stage_from_artifacts(row: Any, tmp_path: Path, cache: Path) -> None:
    base = _base(tmp_path)
    wt = _task(base, "demo")
    _make_artifacts(wt, "demo", list(row.input["artifacts"]), cache)
    _write_spans(
        base, [_span(base, "demo", e, s, "s1", i) for i, (e, s) in enumerate(row.input["spans"])]
    )
    d = _digest_mod().digest(base, session_id="s1")
    assert _task_entry(d, "demo")["next_stage"] == row.expected["next_stage"]


def test_ac003_newest_review_decides(tmp_path: Path, cache: Path) -> None:
    """An older APPROVED review must not count once a newer review is in progress."""
    base = _base(tmp_path)
    wt = _task(base, "demo")
    _make_artifacts(wt, "demo", ["spec_exempt", "plan"], cache)
    docs = wt / "work-docs"
    (docs / "REVIEW-demo-2026-10-01.md").write_text(
        "---\nstatus: APPROVED\n---\n", encoding="utf-8"
    )
    (docs / "REVIEW-demo-2026-10-02.md").write_text(
        "---\nstatus: in-progress\n---\n", encoding="utf-8"
    )
    assert _task_entry(_digest_mod().digest(base), "demo")["next_stage"] == "review"


def test_ac003_stale_verify_marker_means_verify(tmp_path: Path, cache: Path) -> None:
    """A marker written before the tree changed does not count as verified."""
    base = _base(tmp_path)
    wt = _task(base, "demo")
    _make_artifacts(wt, "demo", ["spec_exempt", "plan", "review_approved", "verify_marker"], cache)
    assert _task_entry(_digest_mod().digest(base), "demo")["next_stage"] == "wrapup"
    (wt / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(wt, "add", "app.py")
    assert _task_entry(_digest_mod().digest(base), "demo")["next_stage"] == "verify"


def test_ac003_plan_only_means_spec(tmp_path: Path, cache: Path) -> None:
    """A PLAN without an approved SPEC is past research but not past spec."""
    base = _base(tmp_path)
    wt = _task(base, "demo")
    _make_artifacts(wt, "demo", ["plan"], cache)
    assert _task_entry(_digest_mod().digest(base), "demo")["next_stage"] == "spec"


# ---------------------------------------------------------------------------
# AC-004 — last stage and other-session flag (golden)
# ---------------------------------------------------------------------------

_AC004 = load_golden_table(_SPEC_YAML, "AC-004")


@pytest.mark.parametrize("row", _AC004, ids=[f"r{i}" for i in range(len(_AC004))])
def test_ac004_last_stage_and_session(row: Any, tmp_path: Path) -> None:
    base = _base(tmp_path)
    _task(base, "demo")
    rows: list[dict[str, Any] | str] = []
    for i, (event, stage, session) in enumerate(row.input["rows"]):
        if event == "TORN":
            rows.append('{"schema_version": 1, "event": "end", "stage": "hm:rev')
        else:
            rows.append(_span(base, "demo", event, stage, session, i))
    _write_spans(base, rows)
    d = _digest_mod().digest(base, session_id=row.input["session"])
    t = _task_entry(d, "demo")
    assert t["last_stage"] == row.expected["last_stage"]
    assert t["other_session"] is row.expected["other_session"]


def test_ac004_newest_of_several_rows_wins(tmp_path: Path) -> None:
    """Two well-formed rows that disagree on stage and session; the newest decides, and
    `last_seen` is its timestamp — even when the ledger holds them out of time order."""
    base = _base(tmp_path)
    _task(base, "demo")
    # Only the timestamp marks the newest row: it is neither first nor last in the file, not the
    # furthest stage, not an `end`, and shares the caller's session — so first-row, last-row,
    # most-advanced-stage, latest-end and any-other-session rules all give a different answer.
    older = _span(base, "demo", "end", "hm:execute", "s2", minutes=5)
    newer = _span(base, "demo", "start", "hm:spec", "s1", minutes=10)
    oldest = _span(base, "demo", "end", "hm:review", "s1", minutes=1)
    _write_spans(base, [older, newer, oldest])
    t = _task_entry(_digest_mod().digest(base, session_id="s1"), "demo")
    assert t["last_stage"] == "spec"
    assert t["other_session"] is False
    assert t["last_seen"] == newer["ts"]


# ---------------------------------------------------------------------------
# AC-005 — tasks are newest-first and capped at five
# ---------------------------------------------------------------------------


def digest_with_tasks(n: int, tmp: Path) -> dict[str, Any]:
    base = _base(tmp)
    rows: list[dict[str, Any] | str] = []
    for i in range(1, n + 1):
        _task(base, f"t{i}")
        rows.append(_span(base, f"t{i}", "start", "hm:spec", "s1", minutes=i))
    _write_spans(base, rows)
    result: dict[str, Any] = _digest_mod().digest(base, session_id="s1")
    return result


def test_ac_005_newest_first_capped(tmp_path: Path) -> None:
    d = digest_with_tasks(7, tmp_path)
    # the approved AC-005 predicate, verbatim
    assert [t["slug"] for t in d["tasks"]] == ["t7", "t6", "t5", "t4", "t3"] and d["more"] == 2  # noqa: PT018


def test_ac005_tasks_without_spans_sort_last(tmp_path: Path) -> None:
    base = _base(tmp_path)
    _task(base, "aaa-quiet")
    _task(base, "zzz-busy")
    _write_spans(base, [_span(base, "zzz-busy", "start", "hm:spec", "s1")])
    d = _digest_mod().digest(base, session_id="s1")
    # alphabetical order would put aaa-quiet first; newest-first puts the task with a span first
    assert [t["slug"] for t in d["tasks"]] == ["zzz-busy", "aaa-quiet"]


def test_ac005_order_follows_last_seen_not_slug(tmp_path: Path) -> None:
    base = _base(tmp_path)
    minutes = {"t1": 70, "t2": 10, "t3": 60, "t4": 20, "t5": 50, "t6": 30, "t7": 40}
    rows: list[dict[str, Any] | str] = []
    for slug, m in minutes.items():
        _task(base, slug)
        rows.append(_span(base, slug, "start", "hm:spec", "s1", minutes=m))
    _write_spans(base, rows)
    d = _digest_mod().digest(base, session_id="s1")
    assert [t["slug"] for t in d["tasks"]] == ["t1", "t3", "t5", "t7", "t6"]
    assert d["more"] == 2


# ---------------------------------------------------------------------------
# AC-006 — digest reads the base ledger from any root (differential)
# ---------------------------------------------------------------------------


def test_ac006_root_resolves_to_base(tmp_path: Path) -> None:
    base = _base(tmp_path)
    wt = _task(base, "demo")
    (base / "sub").mkdir()
    _write_spans(base, [_span(base, "demo", "start", "hm:execute", "s1")])
    outs = [
        _run_cli("digest", "--root", str(r), "--session-id", "s1") for r in (base, base / "sub", wt)
    ]
    assert all(rc == 0 for rc, _ in outs)
    payloads = [json.loads(o) for _, o in outs]
    assert payloads[0] == payloads[1] == payloads[2]
    assert _task_entry(payloads[0], "demo")["last_stage"] == "execute"


# ---------------------------------------------------------------------------
# AC-009 — digest intent items match hm intent status (differential)
# ---------------------------------------------------------------------------

_IDS = st.lists(st.from_regex(r"[A-Z][A-Z0-9-]{0,12}", fullmatch=True), max_size=6, unique=True)


@settings(
    max_examples=40,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    conflicts=_IDS,
    fired=_IDS,
    reval=_IDS,
    stale=st.dictionaries(
        st.from_regex(r"[a-z]{1,8}", fullmatch=True),
        st.sampled_from(["changed", "missing"]),
        max_size=5,
    ),
)
def test_ac009_intents_match_status(
    shared_base: Path,
    monkeypatch: pytest.MonkeyPatch,
    conflicts: list[str],
    fired: list[str],
    reval: list[str],
    stale: dict[str, str],
) -> None:
    from harness_maker import intent_cli

    status = {
        "state": "ok",
        "conflicts": conflicts,
        "fired_revisits": fired,
        "needs_revalidation": reval,
        "stale_evidence": stale,
    }
    (shared_base / ".claude").mkdir(exist_ok=True)
    (shared_base / ".claude/intent.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    monkeypatch.setattr(intent_cli, "status_report", lambda _root: dict(status))
    intents = _digest_mod().digest(shared_base, session_id=None)["intents"]
    expected_counts = {
        "conflicts": len(conflicts),
        "fired_revisits": len(fired),
        "needs_revalidation": len(reval),
        "stale_evidence": len(stale),
    }
    assert intents["counts"] == expected_counts
    reference = set(conflicts) | set(fired) | set(reval) | set(stale)
    assert len(intents["items"]) <= 3
    assert set(intents["items"]) <= reference
    assert len(intents["items"]) == min(3, len(reference))


def test_hm_console_script_dispatches_world_model_digest(tmp_path: Path) -> None:
    """The shipped spelling `hm world_model digest` reaches the module (dispatch allowlist +
    command registry), from inside a task worktree."""
    import sys

    base = _base(tmp_path)
    wt = _task(base, "demo")
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "world_model", "digest", "--root", str(wt)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert [t["slug"] for t in json.loads(proc.stdout)["tasks"]] == ["demo"]


def test_review_fix_hyphen_prefix_slug_ignores_sibling_artifacts(
    tmp_path: Path, cache: Path
) -> None:
    """REVIEW a003ff68 window: task `demo` must not read `demo-two`'s REVIEW/SPEC files."""
    base = _base(tmp_path)
    wt = _task(base, "demo")
    _make_artifacts(wt, "demo-two", ["spec_exempt", "plan", "review_approved"], cache)
    assert _task_entry(_digest_mod().digest(base), "demo")["next_stage"] == "research"


def test_review_fix_artifact_checks_only_for_shown_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW 6d4374d1 window: 7 tasks → next_stage evaluated for the 5 shown, and a blown
    deadline yields null instead of a stalled briefing."""
    mod = _digest_mod()
    calls: list[str] = []

    def fake_next_stage(_base: Path, slug: str, _wt: Path) -> str:
        calls.append(slug)
        return "spec"

    monkeypatch.setattr(mod, "next_stage", fake_next_stage)
    d = digest_with_tasks(7, tmp_path / "a")
    assert sorted(calls) == sorted(t["slug"] for t in d["tasks"])
    assert len(calls) == 5
    monkeypatch.setattr(mod, "DEADLINE_S", -1.0)
    d2 = digest_with_tasks(2, tmp_path / "b")
    assert [t["next_stage"] for t in d2["tasks"]] == [None, None]
