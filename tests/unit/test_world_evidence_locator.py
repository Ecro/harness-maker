"""SPEC-assumption-entry-and-evidence-locator — the evidence locator (AC-003 … AC-007, AC-009).

The oracle for every fingerprint below is the SPEC Constraints "Normalization" row, restated here
as `_expected_fp` and as a hand-computed literal (`EXPECTED_FP`) — never the module under test.
Phase 1 covers the pure module (`capture` / `classify` / `shape_error` / the property); Phases 2–3
add the world-level rows (add/observe with a locator, gap derivation, propagation).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from harness_maker import evidence_locator as el

settings.register_profile("ci", derandomize=True, max_examples=60, deadline=None)
settings.register_profile("dev", max_examples=300, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

#: sha256("def total(a, b):\nreturn a + b") — lines 10–12 of `_FIXTURE_LINES` normalized by hand
#: (line 12 is blank and drops out, so k == 2). Computed once with hashlib, pasted here.
EXPECTED_FP = "85d385d14503abe7602f8a02b4688b58a264405ec7bcc2a46cf04a209a19496a"
EXPECTED_LOCATOR = {"path": "src/m.py", "lines": [10, 12], "fingerprint": EXPECTED_FP, "k": 2}


def _fixture_lines() -> list[str]:
    lines = [f"v{i} = {i}" for i in range(1, 31)]
    lines[9] = "def total(a,  b):"
    lines[10] = "    return  a + b"
    lines[11] = ""
    return lines


def _write(root: Path, lines: list[str], rel: str = "src/m.py") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _expected_fp(lines: list[str]) -> str:
    """SPEC Constraints 'Normalization', restated independently of the module."""
    kept = [" ".join(line.split()) for line in lines]
    return hashlib.sha256("\n".join(k for k in kept if k).encode("utf-8")).hexdigest()


# ── AC-003 (pure half): capture builds the locator and refuses bad citations ─────────────────


def test_ac_003_capture_builds_the_locator_from_the_cited_span(tmp_path: Path) -> None:
    _write(tmp_path, _fixture_lines())
    assert el.capture(tmp_path, "src/m.py:10-12") == EXPECTED_LOCATOR


@pytest.mark.parametrize(
    ("spec", "setup"),
    [
        ("src/nope.py:1-2", None),  # missing path
        ("/etc/passwd:1-2", None),  # absolute
        ("src/../src/m.py:10-12", None),  # `..` segment
        ("src/m.py:12-10", None),  # A > B
        ("src/m.py:0-3", None),  # A < 1
        ("src/m.py:29-31", None),  # B past EOF (30 lines)
        ("src/m.py:1-41", "long"),  # span over 40 lines
        ("src/m.py:12-12", None),  # all-blank span
        ("src/bin.py:1-1", "binary"),  # not UTF-8
        ("src/m.py", None),  # no span
        ("src/m.py:a-b", None),  # non-integer span
        pytest.param("src/m.py:" + "9" * 5000 + "-1", None, id="digits-past-int-limit"),
        ("src:1-1", "dir"),  # not a file
    ],
)
def test_ac_003_capture_refuses_bad_citations(tmp_path: Path, spec: str, setup: str | None) -> None:
    _write(tmp_path, _fixture_lines())
    if setup == "long":
        _write(tmp_path, [f"line {i}" for i in range(1, 61)])
    if setup == "binary":
        (tmp_path / "src" / "bin.py").write_bytes(b"\xff\xfe\x00bad\n")
    with pytest.raises(el.LocatorError) as info:
        el.capture(tmp_path, spec)
    assert info.value.field == "locator"


def test_ac_003_capture_refuses_a_path_that_resolves_outside_the_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside.py"
    outside.write_text("secret = 1\n", encoding="utf-8")
    (root / "src").mkdir(parents=True)
    (root / "src" / "link.py").symlink_to(outside)
    with pytest.raises(el.LocatorError):
        el.capture(root, "src/link.py:1-1")


def test_ac_003_capture_turns_an_unreadable_file_into_a_locator_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, _fixture_lines())

    def denied(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(13, "denied", str(self))

    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(el.LocatorError):
        el.capture(tmp_path, "src/m.py:10-12")


# ── AC-004: the fingerprint is whitespace-invariant and token-sensitive (property) ──────────

_WORD = st.text(alphabet="abcxyz019_(){}=+-.", min_size=1, max_size=6)
_LINE = st.lists(_WORD, min_size=0, max_size=5).map(" ".join)
_LINES = st.lists(_LINE, min_size=1, max_size=8)


@given(
    lines=_LINES,
    indent=st.lists(st.sampled_from(["", " ", "  ", "\t", " \t "]), min_size=8, max_size=8),
    trailing=st.lists(st.sampled_from(["", " ", "\t", "   "]), min_size=8, max_size=8),
    blanks=st.lists(st.integers(min_value=0, max_value=8), max_size=3),
    crlf=st.booleans(),
)
def test_ac_004_fingerprint_whitespace_invariant(
    lines: list[str], indent: list[str], trailing: list[str], blanks: list[int], crlf: bool
) -> None:
    assume(any(line.strip() for line in lines))
    perturbed = [indent[i].join(["", w]) if w else w for i, w in enumerate(lines)]  # re-indent
    perturbed = [p.replace(" ", "  ") + trailing[i] for i, p in enumerate(perturbed)]
    for pos in sorted(blanks, reverse=True):
        perturbed.insert(min(pos, len(perturbed)), "   ")
    if crlf:
        perturbed = "\r\n".join(perturbed).splitlines()
    assert el.fingerprint(perturbed) == el.fingerprint(lines) == _expected_fp(lines)


@given(lines=_LINES, which=st.integers(min_value=0), where=st.integers(min_value=0))
def test_ac_004_fingerprint_changes_on_any_token_edit(
    lines: list[str], which: int, where: int
) -> None:
    candidates = [i for i, line in enumerate(lines) if line.strip()]
    assume(candidates)
    idx = candidates[which % len(candidates)]
    chars = [j for j, c in enumerate(lines[idx]) if not c.isspace()]
    pos = chars[where % len(chars)]
    old = lines[idx][pos]
    new = "Q" if old != "Q" else "R"
    edited = [*lines]
    edited[idx] = lines[idx][:pos] + new + lines[idx][pos + 1 :]
    assert el.fingerprint(edited) != el.fingerprint(lines)


# ── classify: fresh / moved / changed / missing, never raising on file state ────────────────


def test_classify_fresh_when_the_span_is_unchanged(tmp_path: Path) -> None:
    _write(tmp_path, _fixture_lines())
    assert el.classify(tmp_path, EXPECTED_LOCATOR) == el.Freshness("fresh", None)


def test_classify_fresh_when_a_blank_line_is_inserted_inside_the_span(tmp_path: Path) -> None:
    lines = _fixture_lines()
    lines.insert(10, "")  # between `def total` and `return`
    _write(tmp_path, lines)
    assert el.classify(tmp_path, EXPECTED_LOCATOR).state == "fresh"


def test_classify_moved_reports_the_new_start_line(tmp_path: Path) -> None:
    lines = _fixture_lines()
    lines[0:0] = ["# a", "# b", "# c"]  # the span now starts at line 13
    _write(tmp_path, lines)
    assert el.classify(tmp_path, EXPECTED_LOCATOR) == el.Freshness("moved", 13)


def test_classify_changed_when_the_text_is_gone(tmp_path: Path) -> None:
    lines = _fixture_lines()
    lines[10] = "    return a - b"
    _write(tmp_path, lines)
    assert el.classify(tmp_path, EXPECTED_LOCATOR).state == "changed"


def test_classify_missing_when_the_file_is_gone(tmp_path: Path) -> None:
    assert el.classify(tmp_path, EXPECTED_LOCATOR).state == "missing"


def test_classify_missing_when_reading_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, _fixture_lines())

    def denied(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(13, "denied", str(self))

    monkeypatch.setattr(Path, "read_text", denied)
    assert el.classify(tmp_path, EXPECTED_LOCATOR).state == "missing"


def test_classify_missing_when_resolve_loops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, _fixture_lines())

    def loop(self: Path, *args: object, **kwargs: object) -> Path:
        raise RuntimeError("Symlink loop")

    monkeypatch.setattr(Path, "resolve", loop)
    assert el.classify(tmp_path, EXPECTED_LOCATOR).state == "missing"


# ── shape_error: the file-independent invariants a stored locator must satisfy ─────────────


@pytest.mark.parametrize(
    "raw",
    [
        {**EXPECTED_LOCATOR, "extra": 1},
        {k: v for k, v in EXPECTED_LOCATOR.items() if k != "k"},
        {**EXPECTED_LOCATOR, "path": ""},
        {**EXPECTED_LOCATOR, "path": "/abs.py"},
        {**EXPECTED_LOCATOR, "path": "a/../b.py"},
        {**EXPECTED_LOCATOR, "lines": [True, 12]},
        {**EXPECTED_LOCATOR, "lines": [10]},
        {**EXPECTED_LOCATOR, "lines": [12, 10]},
        {**EXPECTED_LOCATOR, "lines": [0, 3]},
        {**EXPECTED_LOCATOR, "lines": [1, 41]},
        {**EXPECTED_LOCATOR, "fingerprint": "ABC"},
        {**EXPECTED_LOCATOR, "fingerprint": EXPECTED_FP.upper()},
        {**EXPECTED_LOCATOR, "k": 0},
        {**EXPECTED_LOCATOR, "k": 4},  # more non-empty lines than the span holds
        {**EXPECTED_LOCATOR, "k": True},
        "src/m.py:10-12",
    ],
)
def test_shape_error_names_every_malformed_locator(raw: object) -> None:
    assert isinstance(el.shape_error(raw), str)


#: sha256(b"alpha"), computed once with hashlib — any lowercase hex64 is a valid shape.
_OTHER_FP = "8ed3f6ad685b959ead7022518e1af76cd816f8e8ec7ccdda1ed4018e8f2223f8"


@pytest.mark.parametrize(
    "raw",
    [
        EXPECTED_LOCATOR,
        # single line, k == span, top-level file
        {"path": "README.md", "lines": [1, 1], "fingerprint": _OTHER_FP, "k": 1},
        # the maximum span (40 lines) with k at its upper bound, deep path
        {"path": "a/b/c/d.py", "lines": [5, 44], "fingerprint": _OTHER_FP, "k": 40},
        # k below the span (blank lines inside), dotfile-ish segment that is not `..`
        {"path": ".claude/world/x.yaml", "lines": [100, 107], "fingerprint": "0" * 64, "k": 3},
    ],
)
def test_shape_error_accepts_every_well_formed_locator(raw: dict[str, object]) -> None:
    """Acceptance is structural: four shapes that share no field value must all pass."""
    assert el.shape_error(raw) is None


# ── AC-003 (world half): add / observe store the locator, refusals write nothing ───────────

_TS = "2026-09-18T00:00:00Z"
_REFUSED_SPECS = [
    "src/nope.py:1-2",
    "/etc/passwd:1-2",
    "src/../src/m.py:10-12",
    "src/m.py:12-10",
    "src/m.py:0-3",
    "src/m.py:29-31",
    "src/m.py:1-41",
    "src/m.py:12-12",
]


def _world_root(tmp_path: Path) -> Path:
    from tests.unit import world_fixture as fx

    root = fx.build_root(tmp_path, assumptions=[fx.assumption("base_claim", claim="B")])
    _write(root, _fixture_lines())
    return root


def test_ac_003_locator_validated_and_fingerprinted(tmp_path: Path) -> None:
    from tests.unit import world_fixture as fx

    root = _world_root(tmp_path)
    added = fx.run_cli(
        [
            "assume",
            "add",
            "cited",
            "--claim",
            "C",
            "--status",
            "known",
            "--text",
            "t",
            "--observed-at",
            _TS,
            "--locator",
            "src/m.py:10-12",
        ],
        root,
    )
    assert added.returncode == 0, added.stdout + added.stderr
    observed = fx.run_cli(
        [
            "assume",
            "observe",
            "base_claim",
            "--relation",
            "confirms",
            "--text",
            "t2",
            "--observed-at",
            _TS,
            "--locator",
            "src/m.py:10-12",
        ],
        root,
    )
    assert observed.returncode == 0, observed.stdout + observed.stderr
    recs = {r["id"]: r for r in fx.load(fx.assumptions_path(root))["assumptions"]}
    assert recs["cited"]["evidence"][-1]["locator"] == EXPECTED_LOCATOR
    assert recs["base_claim"]["evidence"][-1]["locator"] == EXPECTED_LOCATOR

    before = fx.assumptions_path(root).read_bytes()
    for spec in _REFUSED_SPECS:
        for argv in (
            [
                "assume",
                "add",
                "other",
                "--claim",
                "C",
                "--status",
                "known",
                "--text",
                "t",
                "--observed-at",
                _TS,
                "--locator",
                spec,
            ],
            [
                "assume",
                "observe",
                "base_claim",
                "--relation",
                "confirms",
                "--text",
                "t",
                "--observed-at",
                _TS,
                "--locator",
                spec,
            ],
        ):
            proc = fx.run_cli(argv, root)
            assert proc.returncode != 0, (spec, argv[1])
            assert "field: locator" in proc.stdout, (spec, argv[1])
            assert fx.assumptions_path(root).read_bytes() == before, (spec, argv[1])


# ── AC-005 … AC-007, AC-009: derivation on `gap`, never on `status` ───────────────────────

#: `status`'s key set, frozen by PLAN-objective-gap-proposal ADR-001 (test_world_gap.py:160).
FROZEN_STATUS_KEYS = {
    "state",
    "mission",
    "outcomes",
    "active",
    "proposed",
    "unknowns",
    "conflicts",
    "fired_revisits",
    "broken_references",
}


def _ev(path: str, observed_at: object, *, locator: bool = True) -> dict[str, object]:
    entry: dict[str, object] = {"text": "t", "observed_at": observed_at, "relation": "confirms"}
    if locator:
        entry["locator"] = {**EXPECTED_LOCATOR, "path": path}
    return entry


def _gap(root: Path) -> dict[str, Any]:
    from tests.unit import world_fixture as fx

    proc = fx.run_cli(["gap", "--json"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return fx.stdout_json(proc)


def _world_bytes(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted((root / ".claude" / "world").rglob("*"))
        if p.is_file()
    }


def _derivation_root(tmp_path: Path) -> Path:
    from tests.unit import world_fixture as fx

    base = _fixture_lines()
    blank = [*base]
    blank.insert(10, "")
    moved = ["# a", "# b", "# c", *base]
    changed = [*base]
    changed[10] = "    return a - b"
    ts = "2026-09-10T00:00:00Z"
    root = fx.build_root(
        tmp_path,
        assumptions=[
            fx.assumption("a_fresh", evidence=[_ev("src/fresh.py", ts)]),
            fx.assumption("a_blank", evidence=[_ev("src/blank.py", ts)]),
            fx.assumption("a_moved", status="assumed", evidence=[_ev("src/moved.py", ts)]),
            fx.assumption("a_changed", evidence=[_ev("src/changed.py", ts)]),
            fx.assumption("a_missing", status="unknown", evidence=[_ev("src/gone.py", ts)]),
            fx.assumption("plain", status="assumed", evidence=[]),
        ],
    )
    _write(root, base, "src/fresh.py")
    _write(root, blank, "src/blank.py")
    _write(root, moved, "src/moved.py")
    _write(root, changed, "src/changed.py")
    return root


def test_ac_005_gap_derives_freshness(tmp_path: Path) -> None:
    from harness_maker import world

    root = _derivation_root(tmp_path)
    before = _world_bytes(root)
    report = _gap(root)
    assert report["stale_evidence"] == {"a_changed": "changed", "a_missing": "missing"}
    assert report["moved_evidence"] == {"a_moved": 13}
    assert report["assumptions"] == {
        "a_blank": "known",
        "a_changed": "known",
        "a_fresh": "known",
        "a_missing": "unknown",
        "a_moved": "assumed",
        "plain": "assumed",
    }
    assert _world_bytes(root) == before
    assert set(world.status_report(root)) == FROZEN_STATUS_KEYS


def test_ac_006_latest_locator_is_authoritative(tmp_path: Path) -> None:
    from tests.unit import world_fixture as fx

    lines = _fixture_lines()
    stale = [*lines]
    stale[10] = "    return a - b"
    root = fx.build_root(
        tmp_path,
        assumptions=[
            # re-confirmed below via the CLI
            fx.assumption("x", evidence=[_ev("src/stale.py", "2026-09-01T00:00:00Z")]),
            # a newer locator-LESS entry neither clears nor causes staleness
            fx.assumption(
                "y",
                evidence=[
                    _ev("src/stale.py", "2026-09-01T00:00:00Z"),
                    _ev("src/stale.py", "2026-09-05T00:00:00Z", locator=False),
                ],
            ),
            # fractional seconds are LATER than the whole second; a string max picks the wrong one
            fx.assumption(
                "frac",
                evidence=[
                    _ev("src/fresh.py", "2026-09-10T00:00:00.500000Z"),
                    _ev("src/stale.py", "2026-09-10T00:00:00Z"),
                ],
            ),
            # an offset stamp compares by instant, not by text
            fx.assumption(
                "offset",
                evidence=[
                    _ev("src/fresh.py", "2026-09-10T00:30:00Z"),
                    _ev("src/stale.py", "2026-09-10T08:00:00+09:00"),
                ],
            ),
            # equal instants: the later entry in the list wins
            fx.assumption(
                "tie",
                evidence=[
                    _ev("src/fresh.py", "2026-09-10T00:00:00Z"),
                    _ev("src/stale.py", "2026-09-10T00:00:00Z"),
                ],
            ),
        ],
    )
    _write(root, lines, "src/fresh.py")
    _write(root, stale, "src/stale.py")
    report = _gap(root)
    assert report["stale_evidence"] == {"x": "changed", "y": "changed", "tie": "changed"}

    old_entry = fx.load(fx.assumptions_path(root))["assumptions"][0]["evidence"][0]
    proc = fx.run_cli(
        [
            "assume",
            "observe",
            "x",
            "--relation",
            "confirms",
            "--text",
            "re-checked",
            "--observed-at",
            "2026-09-18T00:00:00Z",
            "--locator",
            "src/fresh.py:10-12",
        ],
        root,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "x" not in _gap(root)["stale_evidence"]
    assert fx.load(fx.assumptions_path(root))["assumptions"][0]["evidence"][0] == old_entry


def test_ac_006_an_unparseable_stamp_is_ignored_and_reported(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from tests.unit import world_fixture as fx

    lines = _fixture_lines()
    stale = [*lines]
    stale[10] = "    return a - b"
    root = fx.build_root(
        tmp_path,
        assumptions=[
            fx.assumption(
                "u",
                evidence=[
                    _ev("src/fresh.py", "2026-09-01T00:00:00Z"),
                    _ev("src/stale.py", "yesterday"),
                    # an unquoted YAML timestamp loads as a datetime, not a str
                    _ev("src/stale.py", datetime(2026, 9, 20, tzinfo=UTC)),
                ],
            )
        ],
    )
    _write(root, lines, "src/fresh.py")
    _write(root, stale, "src/stale.py")
    report = _gap(root)
    assert "u" not in report["stale_evidence"]
    refs = " ".join(report["broken_references"])
    assert "assumptions[0].evidence[1].observed_at" in refs
    assert "assumptions[0].evidence[2].observed_at" in refs


def test_ac_007_staleness_propagates_to_objectives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness_maker import world
    from tests.unit import world_fixture as fx

    stale = _fixture_lines()
    stale[10] = "    return a - b"
    closed: dict[str, Any] = {
        "observed": "met",
        "note": "done",
        "closed_at": "2026-09-03T00:00:00Z",
    }
    root = fx.build_root(
        tmp_path,
        assumptions=[fx.assumption("x", evidence=[_ev("src/stale.py", "2026-09-01T00:00:00Z")])],
        objectives=[
            fx.objective("P", state="proposed", depends_on=["x"]),
            fx.objective("A", state="active", depends_on=["x"]),
            fx.objective("C", state="closed", depends_on=["x"], **closed),
            fx.objective("D", state="dropped", depends_on=["x"]),
        ],
    )
    _write(root, stale, "src/stale.py")
    assert sorted(_gap(root)["needs_revalidation"]) == ["A", "P"]

    w = world.load_world(root)
    stale_map = world.staleness(w)
    assert world.derive(w, "A", staleness=stale_map).needs_revalidation is True
    assert world.derive(w, "C", staleness=stale_map).needs_revalidation is False

    def boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("classify must not run without a staleness map")

    monkeypatch.setattr(el, "classify", boom)
    assert world.derive(w, "A").needs_revalidation is False
    world.status_report(root)  # the frozen read path never classifies


def test_ac_009_a_locator_entry_without_observed_at_is_reported_not_fatal(tmp_path: Path) -> None:
    """ADR-008 covers the missing key too: the pre-existing required-key rule used to drop the
    whole file, so an unrelated assumption and its dependent objective went down with it."""
    from harness_maker import world
    from tests.unit import world_fixture as fx

    ev = {"text": "t", "relation": "confirms", "locator": EXPECTED_LOCATOR}
    root = fx.build_root(
        tmp_path,
        assumptions=[fx.assumption("x", evidence=[ev]), fx.assumption("y")],
        objectives=[fx.objective("OBJ", state="proposed", depends_on=["y"])],
    )
    _write(root, _fixture_lines())
    loaded = world.load_world(root)
    assert set(loaded.assumptions) == {"x", "y"}
    assert "OBJ" not in loaded.broken
    report = _gap(root)
    assert "x" not in report["stale_evidence"]
    assert "assumptions[0].evidence[0].observed_at" in " ".join(report["broken_references"])

    # Newly reachable: writers now load this file instead of refusing it — the entry survives.
    world.observe(root, "y", text="t2", observed_at="2026-09-18T00:00:00Z", relation="confirms")
    x_after = {r["id"]: r for r in fx.load(fx.assumptions_path(root))["assumptions"]}["x"]
    assert x_after["evidence"] == [ev]

    no_locator = fx.build_root(
        tmp_path / "plain",
        assumptions=[fx.assumption("z", evidence=[{"text": "t", "relation": "confirms"}])],
    )
    assert world.validate_assumptions(fx.assumptions_path(no_locator)) != []


def test_ac_009_v1_file_without_locator_loads(tmp_path: Path) -> None:
    from harness_maker import world
    from tests.unit import world_fixture as fx

    v1 = fx.build_root(tmp_path / "v1", assumptions=[fx.assumption()])
    assert world.validate_assumptions(fx.assumptions_path(v1)) == []
    assert _gap(v1)["stale_evidence"] == {}

    bad_ev = _ev("src/m.py", "2026-09-01T00:00:00Z")
    bad_ev["locator"] = {k: v for k, v in EXPECTED_LOCATOR.items() if k != "k"}
    bad = fx.build_root(
        tmp_path / "bad",
        assumptions=[fx.assumption("x", evidence=[bad_ev])],
        objectives=[fx.objective("OBJ", state="proposed", depends_on=["x"])],
    )
    _write(bad, _fixture_lines())
    refs = " ".join(_gap(bad)["broken_references"])
    assert "assumptions[0].evidence[0].locator" in refs
    loaded = world.load_world(bad)
    assert "x" in loaded.assumptions
    assert "OBJ" not in loaded.broken
