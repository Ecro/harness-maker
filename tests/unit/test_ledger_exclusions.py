"""AC-002 / ADR-007 — one exclusion schema, read by both ledgers through one helper.

The defect: `.ledger-exclusions.json` is documented and used as a map of **run ids** to
reasons, and every filter keys on `row["run_id"]`. But `codex_ledger.SecondOpinionRecord`
is `strict=True, extra="forbid"` and has no `run_id` field at all, so the second-opinion
`report` path already tried to exclude and excluded nothing — silently. The 83 synthetic
`slug: "s"` rows are unreachable by a run-id key and always were.

ADR-007 promotes the file to a list of per-entry predicates
`{key: "run_id"|"slug"|"stage", value, reason}` and keeps the legacy single map readable as
run-id entries, so the existing `aiexit-exec-p2b` exclusion keeps its exact meaning and no
file has to be rewritten on disk (which is also what keeps Phase 1 revertible).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import harness_maker.ledger_exclusions as lx


def _write(dirpath: Path, payload: object) -> Path:
    path = dirpath / ".ledger-exclusions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_absent_file_excludes_nothing_but_a_present_one_does_not(tmp_path: Path) -> None:
    """Both halves in one test, so `def load(p): return []` cannot satisfy it.

    The absent-file case alone is the weakest assertion in this module — a stub that never
    opens a file passes it immediately, and the collection-level ImportError that made every
    test in this module RED hides that from Phase B. Pairing it with a populated sibling
    directory makes the constant `[]` a claim about the input rather than about the return.
    """
    empty = tmp_path / "empty"
    empty.mkdir()
    populated = tmp_path / "populated"
    populated.mkdir()
    _write(populated, [{"key": "slug", "value": "s", "reason": "unit-suite synthetic"}])

    assert lx.load(empty) == []
    assert len(lx.load(populated)) == 1


def test_legacy_map_is_read_as_run_id_entries(tmp_path: Path) -> None:
    """The migration is a READ, not a rewrite.

    Nothing on disk changes, so reverting this phase leaves the pre-existing reader looking
    at the file it has always understood. A rewrite would hand a rolled-back reader a JSON
    list, whose `"x" in [...]` membership test silently matches nothing — the exact
    'excluding nothing looks like having nothing to exclude' failure this file exists to
    prevent.
    """
    _write(tmp_path, {"aiexit-exec-p2b": "PASS emitted before its round was dispatched"})

    entries = lx.load(tmp_path)

    assert [(e.key, e.value) for e in entries] == [("run_id", "aiexit-exec-p2b")]
    assert "before its round" in entries[0].reason


def test_predicate_list_is_read_verbatim(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            {"key": "slug", "value": "s", "reason": "synthetic rows from the unit suite"},
            {"key": "run_id", "value": "aiexit-exec-p2b", "reason": "premature PASS"},
        ],
    )

    entries = lx.load(tmp_path)

    assert [(e.key, e.value) for e in entries] == [("slug", "s"), ("run_id", "aiexit-exec-p2b")]


def test_a_slug_entry_excludes_a_second_opinion_row_that_has_no_run_id(tmp_path: Path) -> None:
    """The whole point: second-opinion rows carry `slug`, never `run_id`."""
    _write(tmp_path, [{"key": "slug", "value": "s", "reason": "unit-suite synthetic"}])
    entries = lx.load(tmp_path)

    synthetic = {"slug": "s", "stage": "review", "model": "codex", "status": "skipped"}
    real = {
        "slug": "review-loop-empirics",
        "stage": "review",
        "model": "codex",
        "status": "invoked",
    }

    assert lx.is_excluded(synthetic, entries) is True
    assert lx.is_excluded(real, entries) is False


def test_a_run_id_entry_still_excludes_a_stage_agent_row(tmp_path: Path) -> None:
    """Both ledgers, one helper — the stage-agents contract must survive the promotion."""
    _write(tmp_path, [{"key": "run_id", "value": "aiexit-exec-p2b", "reason": "premature PASS"}])
    entries = lx.load(tmp_path)

    assert lx.is_excluded({"run_id": "aiexit-exec-p2b", "agent": "test-reviewer"}, entries) is True
    assert lx.is_excluded({"run_id": "wtts-exec-a1", "agent": "test-reviewer"}, entries) is False


def test_the_key_names_which_field_is_compared(tmp_path: Path) -> None:
    """The cross-field case — without it, a `key`-blind matcher passes every other test.

    Every other row/value pair here was chosen so the value collides with exactly one field,
    so `any(str(v) == entry.value for v in row.values())` would return the expected boolean
    throughout. `key` is the whole point of ADR-007's schema; a matcher that ignores it drops
    a legitimate row whose `stage` happens to equal an excluded slug — silent under-counting
    in the aggregate this phase exists to make honest.
    """
    row = {"slug": "real-task", "stage": "review", "model": "codex"}

    _write(tmp_path, [{"key": "slug", "value": "review", "reason": "cross-field negative"}])
    assert lx.is_excluded(row, lx.load(tmp_path)) is False, (
        "'review' is this row's STAGE, not its slug — a slug-keyed entry must not match it"
    )

    _write(tmp_path, [{"key": "stage", "value": "review", "reason": "cross-field positive"}])
    assert lx.is_excluded(row, lx.load(tmp_path)) is True


def test_a_row_missing_the_keyed_field_is_not_excluded(tmp_path: Path) -> None:
    """Absent field must not coerce to a match.

    `str(row.get("run_id"))` yields the literal `"None"`, so an exclusions entry whose value
    happened to be `"None"` would drop every row that lacks the field. Keying on a genuinely
    absent value is not a match.
    """
    _write(tmp_path, [{"key": "run_id", "value": "None", "reason": "adversarial"}])
    entries = lx.load(tmp_path)

    assert lx.is_excluded({"slug": "s", "stage": "review"}, entries) is False


def test_malformed_file_is_loud_and_excludes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fail-OPEN with a shout, deliberately — and this corrects the PLAN's ADR-007.

    ADR-007's consequence bullet said a malformed file must 'fail loudly, not fail open'.
    The shipped behaviour it was written against already reasons the other way, in
    `verifier_discrimination`'s own test: *'Fail-open here on purpose: a torn exclusions
    file must not silently empty the report.'* Fail-CLOSED would exclude everything and
    empty the aggregate — a worse and quieter outcome than reporting unfiltered rows next to
    a stderr line. What the ADR actually forbids is silence, and the shout is what supplies
    it. Preserved, not changed.
    """
    (tmp_path / ".ledger-exclusions.json").write_text("{not json", encoding="utf-8")

    assert lx.load(tmp_path) == []
    assert "NO rows excluded" in capsys.readouterr().err


def test_an_unknown_key_is_rejected_loudly_and_the_rest_survive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A typo'd key must not silently exclude nothing while looking configured."""
    _write(
        tmp_path,
        [
            {"key": "sluggg", "value": "s", "reason": "typo"},
            {"key": "slug", "value": "s", "reason": "unit-suite synthetic"},
        ],
    )

    entries = lx.load(tmp_path)

    assert [(e.key, e.value) for e in entries] == [("slug", "s")]
    assert "sluggg" in capsys.readouterr().err


def test_a_list_entry_that_is_not_an_object_is_skipped_loudly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One of two loud branches that had no test at all — a lens found both."""
    _write(tmp_path, [["key", "slug"], {"key": "slug", "value": "s", "reason": "real"}])

    entries = lx.load(tmp_path)

    assert [(e.key, e.value) for e in entries] == [("slug", "s")]
    assert "is not an object" in capsys.readouterr().err


def test_a_top_level_scalar_is_loud_and_excludes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "nope")

    assert lx.load(tmp_path) == []
    assert "neither a list nor an object" in capsys.readouterr().err


def test_an_entry_without_a_value_is_skipped_loudly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing and null both used to produce an inert predicate, silently.

    `""` matches only a row whose field is the empty string; `None` becomes the literal
    string `"None"`. Either way the file looks configured and excludes nothing — the exact
    condition this mechanism exists to end, reachable by one omitted field.
    """
    _write(
        tmp_path,
        [
            {"key": "slug", "reason": "no value at all"},
            {"key": "slug", "value": None, "reason": "explicit null"},
            {"key": "slug", "value": "s", "reason": "the good one"},
        ],
    )

    entries = lx.load(tmp_path)

    assert [(e.key, e.value) for e in entries] == [("slug", "s")]
    assert capsys.readouterr().err.count("no usable 'value'") == 2


def test_an_entry_without_a_reason_is_kept_but_announced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unexplained exclusion still excludes — but ADR-007 requires the reason, so its
    absence must not be silent."""
    _write(tmp_path, [{"key": "slug", "value": "s"}])

    entries = lx.load(tmp_path)

    assert [(e.key, e.value) for e in entries] == [("slug", "s")]
    assert "unauditable" in capsys.readouterr().err


def test_a_single_new_schema_object_is_not_read_as_a_legacy_map(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The likeliest authoring mistake for the promoted vocabulary.

    Read as a legacy map, `{"key": "slug", "value": "s", "reason": "..."}` becomes THREE
    run_id exclusions whose values are `"slug"`, `"s"` and the reason text — matching nothing,
    announcing nothing. A lens traced it: the dict branch had no shape check.
    """
    _write(tmp_path, {"key": "slug", "value": "s", "reason": "forgot the brackets"})

    assert lx.load(tmp_path) == []
    assert "Wrap it in a list" in capsys.readouterr().err
