"""SPEC-maker-front-door-improvements: active intents, maker_load, parked, latest_artifact.

AC-006 (S3) is differential: every metric field is compared against `intent_cli.status_report`,
the existing implementation behind `hm intent status --json`, computed by the test on the same
project. AC-012 (S8) and AC-015 (S11) are properties whose oracle is computed from the generated
fixture itself (artifact set, frontmatter `created`, commit count, `os.utime` mtimes). AC-011
(S7) pins the `maker_load` row shape fixed by the DRI decision / ADR-003.

Fixtures are real git repos with real `hm/<slug>` worktrees; intent records are written in the
canonical layout (`.claude/intent.yaml` with `purpose`, `intent/<ID>.md`), and measurements go
through the shipped `hm intent metric record` verb. Profiles: `ci` (derandomized, the gate) and
`dev` (broader), selected by HYPOTHESIS_PROFILE (default ci).
"""

from __future__ import annotations

import importlib
import io
import json
import os
import subprocess
from contextlib import redirect_stdout
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import HealthCheck, Phase, example, given, settings
from hypothesis import strategies as st

# Every example builds a git repo with worktrees: shrinking a failure costs Hypothesis's full
# ~300 s shrink budget per test (measured), so the gate profile reports the first failing
# example unshrunk. `dev` keeps shrinking for diagnosis.
settings.register_profile(
    "ci",
    derandomize=True,
    max_examples=40,
    deadline=None,
    phases=(Phase.explicit, Phase.reuse, Phase.generate),
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "dev",
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

MAX_BYTES = 1500
DASH = "—"
ARTIFACTS = ("RESEARCH", "SPEC", "PLAN", "REVIEW")


# ── shared builders (patterns copied from test_world_model_digest.py) ────────────────────────


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=30
    )
    return proc.stdout


def _base(tmp: Path, subjects: tuple[str, ...] = ()) -> Path:
    base = tmp / "base"
    base.mkdir(parents=True)
    _git(base, "init", "-q")
    _git(base, "config", "user.name", "t")
    _git(base, "config", "user.email", "t@t")
    _git(base, "commit", "-q", "--allow-empty", "-m", "init")
    for s in subjects:
        _git(base, "commit", "-q", "--allow-empty", "-m", s)
    return base


def _task(base: Path, slug: str) -> Path:
    wt = base / ".worktrees" / slug
    _git(base, "worktree", "add", "-q", "-b", f"hm/{slug}", str(wt))
    return wt


def _run_digest(root: Path, session_id: str | None = None) -> tuple[int, str]:
    wm = importlib.import_module("harness_maker.world_model")
    argv = ["digest", "--root", str(root)]
    if session_id is not None:
        argv += ["--session-id", session_id]
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = wm.main(argv)
    return int(rc or 0), buf.getvalue()


def _rendered(root: Path) -> tuple[str, dict[str, Any]]:
    rc, out = _run_digest(root, "s1")
    assert rc == 0
    text = out.strip()
    payload = json.loads(text)
    assert isinstance(payload, dict)
    assert "unavailable" not in payload, payload
    return text, payload


def _artifact_path(wt: Path, slug: str, kind: str) -> Path:
    """The names `world_model_digest.next_stage` already recognises."""
    return {
        "RESEARCH": wt / "work-docs" / f"RESEARCH-{slug}.md",
        "SPEC": wt / "specs" / f"SPEC-{slug}.md",
        "PLAN": wt / "work-docs" / f"PLAN-{slug}.md",
        "REVIEW": wt / "work-docs" / f"REVIEW-{slug}-2026-10-02.md",
    }[kind]


def _write_artifact(wt: Path, slug: str, kind: str, *, created: date | None = None) -> Path:
    path = _artifact_path(wt, slug, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    front = [f"type: {kind.lower()}", f"task_slug: {slug}"]
    if kind == "REVIEW":
        front.append("status: in-progress")
    if created is not None:
        front.append(f"created: {created.isoformat()}")
    path.write_text("---\n" + "\n".join(front) + "\n---\n# body\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AC-006 — active intents within the byte cap (property, differential)
# ---------------------------------------------------------------------------

_METRIC_KINDS = ("measured", "never", "stale")
_metric_id = st.from_regex(r"[a-z][a-z0-9_]{0,29}", fullmatch=True)
_objective_id = st.from_regex(r"[A-Z][A-Z0-9-]{0,79}", fullmatch=True)
_HANGUL = st.text(alphabet=st.sampled_from(list("가나다라마바사아자차카타파하 ")), max_size=40)
_task_slug = st.from_regex(r"[a-z][a-z0-9]{0,39}", fullmatch=True)


@st.composite
def _intent_world(draw: st.DrawFn) -> dict[str, Any]:
    metric_ids = draw(st.lists(_metric_id, min_size=1, max_size=4, unique=True))
    metrics = [
        {
            "id": mid,
            "kind": draw(st.sampled_from(_METRIC_KINDS)),
            "target": draw(st.integers(0, 1000)),
            "value": draw(st.integers(-50, 2000)),
            "higher_is_better": draw(st.booleans()),
        }
        for mid in metric_ids
    ]
    ids = draw(st.lists(_objective_id, max_size=22, unique=True))
    n_active = draw(st.integers(0, min(20, len(ids))))
    intents = [
        {
            "id": oid,
            "state": "active" if i < n_active else "proposed",
            "metric_id": draw(st.sampled_from(metric_ids)),
            "title": draw(_HANGUL),
        }
        for i, oid in enumerate(ids)
    ]
    slugs = draw(st.lists(_task_slug, max_size=8, unique=True))
    subjects = tuple(draw(st.lists(_HANGUL.map(lambda s: s * 4 + "x"), max_size=2)))
    return {"metrics": metrics, "intents": intents, "slugs": slugs, "subjects": subjects}


def _intent_yaml(metrics: list[dict[str, Any]], *, bump_stale: bool) -> str:
    doc = {
        "schema_version": 1,
        "owners": {},
        "metrics": [
            {
                "id": m["id"],
                "description": f"{m['id']} 설명",
                # A stale metric's definition changes after its value was recorded.
                "target": m["target"] + (1 if bump_stale and m["kind"] == "stale" else 0),
                "higher_is_better": m["higher_is_better"],
                "how_measured": "count by hand",
            }
            for m in metrics
        ],
        "rules": [],
        "out_of_scope": [],
        "purpose": {"statement": "ship the fixture", "vision": "a fixture that ships"},
        "open_questions": [],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def _intent_record(intent: dict[str, Any], target: int) -> dict[str, Any]:
    from harness_maker import world

    rec: dict[str, Any] = {
        "id": intent["id"],
        "title": intent["title"].strip() or "제목",
        "scope": ["fixture scope"],
        "state": intent["state"],
        "created_at": "2026-09-01T00:00:00Z",
        "schema_version": 1,
        "rejected": [],
        "depends_on": [],
        "approval": None,
        "revisit_when": None,
        "observed": None,
        "note": None,
        "closed_at": None,
        "statement": "fixture statement",
        "metric_id": intent["metric_id"],
        "out_of_scope": [],
    }
    if intent["state"] == "active":
        rec["approval"] = {
            "content_hash": world.approval_hash(rec, target),
            "approved_by": "t",
            "approved_at": "2026-09-02T00:00:00Z",
            "approved_target": target,
        }
    return rec


def _build_intent_project(tmp: Path, w: dict[str, Any]) -> Path:
    from harness_maker import intent_cli

    base = _base(tmp, w["subjects"])
    claude = base / ".claude"
    (claude / "observability").mkdir(parents=True)
    intent_yaml = claude / "intent.yaml"
    intent_yaml.write_text(_intent_yaml(w["metrics"], bump_stale=False), encoding="utf-8")
    for m in w["metrics"]:
        if m["kind"] in ("measured", "stale"):
            with redirect_stdout(io.StringIO()):
                rc = intent_cli.main(
                    [
                        "--root",
                        str(base),
                        "metric",
                        "record",
                        m["id"],
                        "--value",
                        str(m["value"]),
                        "--evidence",
                        "fixture",
                    ]
                )
            assert rc == 0, m
    intent_yaml.write_text(_intent_yaml(w["metrics"], bump_stale=True), encoding="utf-8")
    targets = {m["id"]: m["target"] + (1 if m["kind"] == "stale" else 0) for m in w["metrics"]}
    for intent in w["intents"]:
        rec = _intent_record(intent, targets[intent["metric_id"]])
        path = base / "intent" / f"{intent['id']}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        fm = yaml.safe_dump(rec, sort_keys=False, allow_unicode=True)
        path.write_text(f"---\n{fm}---\n## Problem\n\nfixture\n", encoding="utf-8")
    for slug in w["slugs"]:
        _task(base, slug)
    return base


def _expected_field(metric: dict[str, Any] | None, field: str) -> Any:
    value = metric.get(field) if metric is not None else None
    return DASH if value is None else value


@given(w=_intent_world())
def test_ac006_active_intents_within_cap(tmp_path_factory: pytest.TempPathFactory, w: Any) -> None:
    from harness_maker import intent_cli

    base = _build_intent_project(tmp_path_factory.mktemp("ac006"), w)
    status = intent_cli.status_report(base)
    assert status.get("state") == "ok", status
    active_ids = list(status["active"])
    # The fixture is valid: every generated active record is active per the reference.
    assert sorted(active_ids) == sorted(i["id"] for i in w["intents"] if i["state"] == "active")
    n_active, n_tasks = len(active_ids), len(w["slugs"])

    text, d = _rendered(base)
    assert len(text.encode("utf-8")) <= MAX_BYTES

    intents = d.get("intents")
    assert isinstance(intents, dict), f"digest has no intents block: {d}"
    if n_active:
        assert "active" in intents, f"intents block lacks `active`: {intents}"
    listed = intents.get("active", [])
    assert isinstance(listed, list)
    listed_ids = [row["id"] for row in listed]
    assert len(listed_ids) == len(set(listed_ids)), listed_ids
    assert len(listed) >= min(3, n_active), (n_active, listed)
    # S3: at least the FIRST three active intents (status order) appear.
    assert set(active_ids[: min(3, n_active)]) <= set(listed_ids), (active_ids, listed_ids)
    for row in listed:
        assert set(row) >= {"id", "metric_id", "last", "target", "gap"}, row
        assert row["id"] in status["active"], row
        metric_id = status["intents"][row["id"]]["metric_id"]
        assert row["metric_id"] == metric_id, row
        metric = status["metrics"].get(metric_id)
        for field in ("last", "target", "gap"):
            assert row[field] == _expected_field(metric, field), (field, row, metric)

    assert len(d["tasks"]) >= min(3, n_tasks), (n_tasks, d["tasks"])


def test_ac006_worst_case_payload_keeps_floors() -> None:
    """REVIEW e84ee34f / 9df6b033 / codex dbe5ddc7: the cap's trim order on a worst case.

    20 active ~80-char intents (some non-ASCII), 8 tasks carrying every optional field, long
    recent subjects: the render must still show >= 3 tasks and >= 3 active intents.
    """
    digest_mod = importlib.import_module("harness_maker.world_model_digest")
    ids = [f"OBJ-{i:02d}-" + ("가나다" if i % 2 else "ÉÜ") + "X" * 76 for i in range(20)]
    at = "2026-10-01T09:00:00+00:00"
    tasks = [
        {
            "slug": f"task-{i}-" + "s" * 32,
            "next_stage": "execute",
            "last_stage": "review",
            "last_seen": at,
            "other_session": False,
            "parked": False,
            "latest_artifact": {"name": f"REVIEW-task-{i}-{'s' * 32}-2026-10-01.md", "at": at},
        }
        for i in range(8)
    ]
    payload = {
        "tasks": tasks,
        "more": 0,
        "autopilot": {"active": True, "level": "auto_safe", "pipeline": ["research", "wrapup"]},
        "recent": ["abc1234 " + "긴 커밋 제목 " * 30] * 3,
        "intents": {
            "counts": dict.fromkeys(
                ("conflicts", "fired_revisits", "needs_revalidation", "stale_evidence"), 20
            ),
            "items": ids[:3],
            "active": [
                {"id": i, "metric_id": "m_" + "x" * 78, "last": 123456, "target": 1000, "gap": -1}
                for i in ids
            ],
        },
    }
    out = digest_mod.render(payload)
    assert len(out.encode("utf-8")) <= MAX_BYTES, len(out.encode("utf-8"))
    d = json.loads(out)
    assert "unavailable" not in d, d
    assert len(d["tasks"]) >= 3, d["tasks"]
    assert len(d["intents"]["active"]) >= 3, d["intents"]
    assert [r["id"][:6] for r in d["intents"]["active"][:3]] == [i[:6] for i in ids[:3]]


def test_ac006_worst_case_end_to_end_through_cli(tmp_path: Path) -> None:
    """REVIEW confirm-1: the worst case through the real `digest` CLI, not `render` alone.

    20 active intents with 80-char ids, 8 task worktrees each carrying every artifact plus span
    rows (so `last_stage`/`last_seen`/`other_session` are all populated), long non-ASCII commit
    subjects. Objective ids are `[A-Z0-9-]+` by schema (world.py `_OBJECTIVE_ID_RE`), so the
    non-ASCII load rides on titles and commit subjects. The trim keeps `other_session` on every
    listed task — Maker reads its absence as "unknown, ask once".
    """
    metrics = [
        {
            "id": f"m{i}_" + "x" * 27,
            "kind": "measured",
            "target": 1000,
            "value": 123456,
            "higher_is_better": True,
        }
        for i in range(2)
    ]
    intents = [
        {
            "id": f"OBJ-{i:02d}-" + "X" * 73,
            "state": "active",
            "metric_id": metrics[i % 2]["id"],
            "title": "가나다라마바사 " * 5,
        }
        for i in range(20)
    ]
    slugs = [f"t{i}" + "s" * 38 for i in range(8)]
    subjects = tuple(f"feat: {'긴 커밋 제목 ' * 20}{n}" for n in range(3))
    w = {"metrics": metrics, "intents": intents, "slugs": slugs, "subjects": subjects}
    base = _build_intent_project(tmp_path, w)
    spans = base / ".claude/observability/stage-spans.jsonl"
    with spans.open("a", encoding="utf-8") as fh:
        for n, slug in enumerate(slugs):
            wt = base / ".worktrees" / slug
            for kind in ARTIFACTS:
                _write_artifact(wt, slug, kind, created=date.today())
            row = {
                "task_slug": slug,
                "stage": "hm:execute",
                "ts": f"2026-10-01T09:{n:02d}:00+00:00",
                "session_id": "s1" if n % 2 else "s2",
            }
            fh.write(json.dumps(row) + "\n")
    assert len(str(intents[0]["id"])) == 80

    text, d = _rendered(base)
    assert len(text.encode("utf-8")) <= MAX_BYTES, len(text.encode("utf-8"))
    assert "unavailable" not in text, text
    assert len(d["tasks"]) >= 3, d["tasks"]
    assert len(d["intents"]["active"]) >= 3, d["intents"]
    for t in d["tasks"]:
        assert "other_session" in t, f"`other_session` trimmed from {t}"
        assert isinstance(t["other_session"], bool), t


# ---------------------------------------------------------------------------
# AC-011 — every digest run records one maker_load row
# ---------------------------------------------------------------------------


def _ledger_rows(base: Path) -> list[dict[str, Any]]:
    path = base / ".claude/observability/world-model.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_ac011_maker_load_row(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    wm = importlib.import_module("harness_maker.world_model")
    base = _base(tmp_path / "a")
    wt = _task(base, "demo")
    (base / ".claude/observability").mkdir(parents=True)

    for n, root in enumerate((base, wt), start=1):
        before = _ledger_rows(base)
        # Second precision: the row's `ts` may be truncated to whole seconds.
        started = datetime.now(UTC).replace(microsecond=0)
        rc = wm.main(["digest", "--root", str(root), "--session-id", "s1"])
        out = capsys.readouterr().out
        assert rc == 0
        assert isinstance(json.loads(out), dict)
        after = _ledger_rows(base)
        assert len(after) == len(before) + 1 == n, (
            f"run {n} from {root}: expected one new maker_load row in "
            f"{base}/.claude/observability/world-model.jsonl, have {after}"
        )
        row = after[-1]
        assert set(row) == {"ts", "event", "session_id"}, row
        assert row["event"] == "maker_load"
        assert row["session_id"] == "s1"
        assert isinstance(row["ts"], str)
        ts = datetime.fromisoformat(row["ts"])
        assert ts.tzinfo is not None, row["ts"]
        assert ts.utcoffset() == timedelta(0), row["ts"]
        assert started <= ts <= datetime.now(UTC), (started, row["ts"])


def test_ac011_no_session_id_records_null(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REVIEW 1159f620 absent case: no `--session-id` still records a row, with a null id."""
    wm = importlib.import_module("harness_maker.world_model")
    base = _base(tmp_path)
    (base / ".claude/observability").mkdir(parents=True)
    rc = wm.main(["digest", "--root", str(base)])
    assert rc == 0
    assert isinstance(json.loads(capsys.readouterr().out), dict)
    rows = _ledger_rows(base)
    assert len(rows) == 1, rows
    assert rows[0]["event"] == "maker_load"
    assert rows[0]["session_id"] is None


def test_ac011_no_claude_dir_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REVIEW 1159f620 absent case: a repo without `.claude/` is not a harness — create nothing."""
    wm = importlib.import_module("harness_maker.world_model")
    base = _base(tmp_path)
    rc = wm.main(["digest", "--root", str(base), "--session-id", "s1"])
    assert rc == 0
    assert isinstance(json.loads(capsys.readouterr().out), dict)
    assert not (base / ".claude").exists()


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores directory permissions"
)
def test_ac011_unwritable_observability_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unwritable observability dir never changes the exit code or the JSON."""
    wm = importlib.import_module("harness_maker.world_model")
    ro_base = _base(tmp_path / "b")
    obs = ro_base / ".claude/observability"
    obs.mkdir(parents=True)
    obs.chmod(0o500)
    try:
        rc = wm.main(["digest", "--root", str(ro_base), "--session-id", "s1"])
        out = capsys.readouterr().out
    finally:
        obs.chmod(0o700)
    assert rc == 0
    payload = json.loads(out)
    assert isinstance(payload, dict)
    assert "tasks" in payload
    assert not (obs / "world-model.jsonl").exists()


# ---------------------------------------------------------------------------
# AC-012 — stale research-only tasks are parked last (property)
# ---------------------------------------------------------------------------

# A local/UTC date disagreement makes the 7/8-day boundary depend on which "today" the
# implementation reads; those two ages are drawn only when both agree (no flaky boundary).
_DATES_AGREE = date.today() == datetime.now(UTC).date()
_AGES = [d for d in range(31) if _DATES_AGREE or d not in (7, 8)]

_artifact_subset = st.frozensets(st.sampled_from(ARTIFACTS))
_task_spec = st.tuples(
    _artifact_subset,
    st.one_of(st.none(), st.sampled_from(_AGES)),
    st.integers(0, 2),
)


def _expected_parked(artifacts: frozenset[str], age: int | None, commits: int) -> bool:
    return artifacts == {"RESEARCH"} and age is not None and age > 7 and commits == 0


@given(specs=st.lists(_task_spec, max_size=8))
@example(
    specs=[
        (frozenset({"RESEARCH"}), 20, 0),  # parked
        (frozenset({"RESEARCH"}), None, 0),  # absent `created` is NOT parked
        (frozenset({"RESEARCH"}), 3, 0),  # fresh
        (frozenset({"RESEARCH"}), 20, 1),  # a commit beyond base unparks
        (frozenset({"RESEARCH", "PLAN"}), 20, 0),  # a later artifact unparks
    ]
)
def test_ac012_parked_sorted_last(
    tmp_path_factory: pytest.TempPathFactory,
    specs: list[tuple[frozenset[str], int | None, int]],
) -> None:
    base = _base(tmp_path_factory.mktemp("ac012"))
    today = date.today()
    expected: dict[str, bool] = {}
    for i, (artifacts, age, commits) in enumerate(specs):
        slug = f"t{i}"
        wt = _task(base, slug)
        for kind in artifacts:
            stamped = kind == "RESEARCH" and age is not None
            created = today - timedelta(days=age or 0) if stamped else None
            _write_artifact(wt, slug, kind, created=created)
        for c in range(commits):
            (wt / f"change-{c}.txt").write_text(f"{c}\n", encoding="utf-8")
            _git(wt, "add", f"change-{c}.txt")
            _git(wt, "commit", "-q", "-m", f"change {c}")
        expected[slug] = _expected_parked(artifacts, age, commits)

    text, d = _rendered(base)
    assert len(text.encode("utf-8")) <= MAX_BYTES
    tasks = d["tasks"]
    assert len(tasks) >= min(3, len(specs))
    for t in tasks:
        assert "parked" in t, f"task row lacks `parked`: {t}"
        assert t["parked"] is expected[t["slug"]], (t, specs[int(t["slug"][1:])])
    flags = [t["parked"] for t in tasks]
    assert flags == sorted(flags), f"a parked task precedes a non-parked one: {flags}"
    # Parked sorts after EVERY non-parked task, so it is only shown once all of those are.
    if any(flags):
        listed = {t["slug"] for t in tasks}
        assert {s for s, p in expected.items() if not p} <= listed, (listed, expected)


# ---------------------------------------------------------------------------
# AC-015 — each task's latest artifact (property)
# ---------------------------------------------------------------------------

_MTIME = st.integers(1_600_000_000, 1_900_000_000)


@st.composite
def _artifact_times(draw: st.DrawFn) -> dict[str, int]:
    kinds = sorted(draw(_artifact_subset))
    times = draw(st.lists(_MTIME, min_size=len(kinds), max_size=len(kinds), unique=True))
    return dict(zip(kinds, times, strict=True))


@given(task_times=st.lists(_artifact_times(), max_size=5))
@example(task_times=[{}, {"RESEARCH": 1_700_000_000, "PLAN": 1_650_000_000}])
def test_ac015_latest_artifact(
    tmp_path_factory: pytest.TempPathFactory, task_times: list[dict[str, int]]
) -> None:
    base = _base(tmp_path_factory.mktemp("ac015"))
    expected: dict[str, dict[str, str] | None] = {}
    for i, times in enumerate(task_times):
        slug = f"t{i}"
        wt = _task(base, slug)
        newest: tuple[int, str] | None = None
        for kind, mtime in times.items():
            path = _write_artifact(wt, slug, kind)
            os.utime(path, (mtime, mtime))
            assert int(os.stat(path).st_mtime) == mtime
            if newest is None or mtime > newest[0]:
                newest = (mtime, path.name)
        expected[slug] = (
            None
            if newest is None
            else {
                "name": newest[1],
                "at": datetime.fromtimestamp(newest[0], UTC).isoformat(timespec="seconds"),
            }
        )

    text, d = _rendered(base)
    assert len(text.encode("utf-8")) <= MAX_BYTES
    tasks = d["tasks"]
    assert len(tasks) >= min(3, len(task_times))
    for t in tasks:
        assert "latest_artifact" in t, f"task row lacks `latest_artifact`: {t}"
        assert t["latest_artifact"] == expected[t["slug"]], (t, task_times)


@pytest.mark.parametrize("groups_dropped", [1, 2], ids=["seen-dropped", "artifact-dropped"])
def test_ac006_trim_drops_optional_fields_in_order_and_keeps_other_session(
    monkeypatch: pytest.MonkeyPatch, groups_dropped: int
) -> None:
    """Post-review (confirm-2 P2): the field-drop step below the 3-task floor is reached and
    ordered — `last_seen`/`last_stage` go first, then `latest_artifact`; `other_session` never
    goes, because Resume reads a missing one as "unknown, ask" and the guard must survive."""
    digest_mod = importlib.import_module("harness_maker.world_model_digest")
    at = "2026-10-01T09:00:00+00:00"
    tasks = [
        {
            "slug": f"t{i}",
            "next_stage": "execute",
            "last_stage": "review",
            "last_seen": at,
            "other_session": True,
            "parked": False,
            "latest_artifact": {"name": f"REVIEW-t{i}-2026-10-01.md", "at": at},
        }
        for i in range(3)
    ]
    payload: dict[str, Any] = {
        "tasks": tasks,
        "more": 0,
        "autopilot": {"active": False},
    }
    monkeypatch.setattr(digest_mod, "MAX_BYTES", 10_000)
    full = json.loads(digest_mod.render(payload))
    expect = json.loads(json.dumps(full))
    for t in expect["tasks"]:
        t.pop("last_seen", None)
        t.pop("last_stage", None)
        if groups_dropped == 2:
            t.pop("latest_artifact", None)
    cap = len(json.dumps(expect, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    monkeypatch.setattr(digest_mod, "MAX_BYTES", cap)
    out = digest_mod.render(payload)
    d = json.loads(out)
    assert len(d["tasks"]) == 3, d
    for t in d["tasks"]:
        assert "last_seen" not in t, t
        assert "last_stage" not in t, t
        assert ("latest_artifact" in t) is (groups_dropped == 1), t
        assert t["other_session"] is True, t
