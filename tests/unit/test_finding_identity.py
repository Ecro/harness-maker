"""Stable finding identity for cross-model records.

PLAN-second-opinion-acceptance-gate ADR-002 rule 4.

Why a dedicated module rather than the `tests/unit/test_codex_adapter.py` the PLAN named:
two adapter modules already exist (`test_codex_finding_adapter.py`,
`test_second_opinion_adapter.py`) and a third same-shaped name would be a coin flip for
the next reader. Identity is its own contract — it spans both vendors' adapters AND the
batch-level collision rule — so it gets its own file.

What the `id` is FOR, and therefore what these tests must pin: the id is simultaneously
(a) the lifecycle key the Auto-Fix Loop uses to mark a frozen record
resolved/stale, (b) the join key between the REVIEW frozen-set section and any fix, and
(c) the `finding_ref` written to the second-opinion ledger. So the two failure modes are
symmetric and both are asserted below:

  * **instability** — an id derived from `file`/`line`/`summary` at *read* time would move
    when a fix moves the code, and the lifecycle update would target the wrong record.
    `test_id_is_frozen_against_later_field_mutation` pins that the id travels as a value.
  * **collision** — a null-location finding has `file`/`line` both None, so its identity
    reduces to (source, message). Two such findings from one model with the same message
    would share an id, silently merging one lifecycle row and double-counting the ledger
    denominator. `test_null_location_same_message_findings_get_distinct_ids` pins the
    batch-scoped suffix. Note this case is NOT hypothetical for this project:
    `.claude/harness.yaml` enables antigravity, whose findings are the null-location-prone
    ones (its CLI has no `--output-schema` to force a location).
"""

from __future__ import annotations

from harness_maker.codex_adapter import (
    adapt_antigravity_finding,
    adapt_antigravity_finding_list,
    adapt_codex_finding,
    adapt_finding_list,
    finding_id,
)

_LOCATED = {
    "severity": "high",
    "file": "src/harness_maker/render.py",
    "line": 88,
    "message": "unguarded dict access",
    "evidence": "cfg['models']",
}

_NULL_LOC = {
    "severity": "critical",
    "file": None,
    "line": None,
    "message": "the guard is applied after the write",
    "evidence": "n/a",
}


def test_both_adapters_emit_an_id() -> None:
    """The id must exist on BOTH vendors — a missing id on one silently disables the
    merge rule for that vendor's records only, which is the hardest variant to notice."""
    assert adapt_codex_finding(_LOCATED)["id"]
    assert adapt_antigravity_finding(_LOCATED)["id"]


def test_id_deterministic_for_identical_input() -> None:
    """Adapting the same payload twice must yield the same id, or a re-read of the frozen
    set after /compact would fail to rejoin its own records."""
    assert adapt_codex_finding(_LOCATED)["id"] == adapt_codex_finding(_LOCATED)["id"]


def test_id_differs_across_models_for_otherwise_identical_finding() -> None:
    """codex and antigravity agreeing on the same defect are TWO voices under K=2. If they
    shared an id the frozen set would keep one and the consensus count would read 1."""
    assert adapt_codex_finding(_LOCATED)["id"] != adapt_antigravity_finding(_LOCATED)["id"]


def test_id_is_frozen_against_later_field_mutation() -> None:
    """The id travels as a value, computed once at adaptation. Mutating file/line/summary
    afterwards (which a fix round does) must not move it."""
    adapted = adapt_codex_finding(_LOCATED)
    before = adapted["id"]
    adapted["file"] = "src/harness_maker/other.py"
    adapted["line"] = 4242
    adapted["summary"] = "reworded by a later round"
    assert adapted["id"] == before


def test_id_differs_when_the_original_location_differs() -> None:
    """Discrimination guard: an id that ignored its inputs would satisfy every test above."""
    moved = {**_LOCATED, "line": 89}
    assert adapt_codex_finding(_LOCATED)["id"] != adapt_codex_finding(moved)["id"]


def test_null_location_same_message_findings_get_distinct_ids() -> None:
    """The collision rule. Two null-location findings from ONE model with the SAME message
    reduce to the same (source, file, line, message) tuple; the batch must still hand out
    distinct ids rather than silently merging them."""
    payload = {"findings": [dict(_NULL_LOC), dict(_NULL_LOC)]}
    ids = [f["id"] for f in adapt_finding_list(payload)]
    assert len(ids) == 2
    assert ids[0] != ids[1], f"batch-scoped collision suffix missing: {ids}"


def test_null_location_collision_rule_applies_to_antigravity_too() -> None:
    """Antigravity is the vendor whose findings are actually null-location-prone, so the
    rule must not be codex-only."""
    payload = {"findings": [dict(_NULL_LOC), dict(_NULL_LOC), dict(_NULL_LOC)]}
    ids = [f["id"] for f in adapt_antigravity_finding_list(payload)]
    assert len(set(ids)) == 3, f"expected 3 distinct ids, got {ids}"


def test_distinct_findings_in_a_batch_keep_their_base_ids() -> None:
    """The suffix must fire ONLY on a real collision. If it were applied unconditionally,
    an id would depend on its position in the batch and stop being reproducible."""
    payload = {"findings": [dict(_LOCATED), dict(_NULL_LOC)]}
    batch = adapt_finding_list(payload)
    assert batch[0]["id"] == adapt_codex_finding(_LOCATED)["id"]
    assert batch[1]["id"] == adapt_codex_finding(_NULL_LOC)["id"]


def test_finding_id_helper_is_pure_and_public() -> None:
    """`/hm:review`'s Step 3 merge point assigns ids to CLAUDE findings with the same
    helper (ADR-002 rule 4's second clause), so it has to be callable on its own."""
    a = finding_id("code-reviewer", "src/a.py", 10, "off-by-one")
    b = finding_id("code-reviewer", "src/a.py", 10, "off-by-one")
    c = finding_id("security-reviewer", "src/a.py", 10, "off-by-one")
    assert a == b
    assert a != c


# ── the CLI the review stage actually calls (REVIEW C2) ────────────────────────────────
#
# The test above proves the FUNCTION is pure. It does not prove the review stage can reach
# it — and it could not: `codex_adapter.main` accepted only `adapt` and exited 2 on anything
# else, while Step 3.4 instructed an LLM turn to compute `sha256(...)[:16]` itself. The only
# available action was to invent an id-shaped string, so Claude-side ids were non-reproducible
# across rounds and the merge-by-`id` rule silently degraded to the `file:line:summary`
# matching ADR-002 rejects. These tests exercise the invocable path, not the helper.


def _run_stamp(payload: str) -> tuple[int, str]:
    import io
    from contextlib import redirect_stdout

    from harness_maker import codex_adapter

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = codex_adapter.main(["stamp-ids"], stdin_text=payload)
    return rc, buf.getvalue()


def test_stamp_ids_cli_agrees_with_the_helper() -> None:
    """The contract that makes Step 3.4 executable: CLI output == `finding_id(...)`.

    A shell reimplementation would diverge — the prose never states
    `separators=(",", ":")` — so agreement has to be asserted against the real function."""
    import json

    findings = [
        {"reviewer": "code-reviewer", "file": "src/a.py", "line": 10, "summary": "off-by-one"},
        {"reviewer": "security-reviewer", "file": None, "line": None, "summary": "unbounded read"},
    ]
    rc, out = _run_stamp(json.dumps({"findings": findings}))
    assert rc == 0, out
    stamped = json.loads(out)["findings"]
    assert stamped[0]["id"] == finding_id("code-reviewer", "src/a.py", 10, "off-by-one")
    assert stamped[1]["id"] == finding_id("security-reviewer", None, None, "unbounded read")


def test_stamp_ids_keeps_an_existing_id() -> None:
    """Re-deriving on later values is the exact bug the id exists to prevent, so a finding
    carried into round 2 must keep the id it was stamped with in round 1."""
    import json

    rc, out = _run_stamp(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "deadbeefdeadbeef",
                        "reviewer": "r",
                        "file": "a",
                        "line": 1,
                        "summary": "s",
                    }
                ]
            }
        )
    )
    assert rc == 0, out
    assert json.loads(out)["findings"][0]["id"] == "deadbeefdeadbeef"


def test_stamp_ids_disambiguates_collisions() -> None:
    import json

    dup = {"reviewer": "r", "file": None, "line": None, "summary": "same"}
    rc, out = _run_stamp(json.dumps({"findings": [dict(dup), dict(dup)]}))
    assert rc == 0, out
    ids = [f["id"] for f in json.loads(out)["findings"]]
    assert ids[0] != ids[1]


def test_stamp_ids_does_not_rename_a_carried_forward_id() -> None:
    """REVIEW F4. The round-2 re-stamp is the documented use: a re-spawned reviewer re-reports
    a finding with no id, and the carried record already has one. Reusing `_disambiguate` here
    renamed the NEW one to `<id>-2`, so the merge-by-`id` join failed and one finding held two
    `pending` records — defeating the contract the stamper was added to serve."""
    import json

    carried = {
        "id": finding_id("r", "a.py", 1, "s"),
        "reviewer": "r",
        "file": "a.py",
        "line": 1,
        "summary": "s",
    }
    reemitted = {"reviewer": "r", "file": "a.py", "line": 1, "summary": "s"}
    rc, out = _run_stamp(json.dumps({"findings": [carried, reemitted]}))
    assert rc == 0, out
    ids = [f["id"] for f in json.loads(out)["findings"]]
    assert ids[0] == carried["id"], "the carried id was renamed"
    assert ids[1] != carried["id"], "the re-emitted finding must not collide with the carried one"


def test_stamp_ids_suffix_never_collides_with_an_existing_id() -> None:
    """REVIEW F4, second half. `_disambiguate` never checked its own OUTPUT against ids already
    taken: for `["abc-2", →"abc", →"abc"]` the third also became `"abc-2"`. That violates §1's
    'never merge two findings onto one id' outright."""
    import json

    base = finding_id("r", None, None, "dup")
    payload = {
        "findings": [
            {"id": f"{base}-2"},
            {"reviewer": "r", "file": None, "line": None, "summary": "dup"},
            {"reviewer": "r", "file": None, "line": None, "summary": "dup"},
        ]
    }
    rc, out = _run_stamp(json.dumps(payload))
    assert rc == 0, out
    ids = [f["id"] for f in json.loads(out)["findings"]]
    assert len(set(ids)) == 3, f"duplicate id minted: {ids}"


def test_stamp_ids_does_not_silently_drop_a_bare_record() -> None:
    """A dict without a `findings` key used to return `{"findings": []}` — a total drop."""
    import json

    rc, out = _run_stamp(json.dumps({"reviewer": "r", "file": "a.py", "line": 1, "summary": "s"}))
    assert rc == 0, out
    assert len(json.loads(out)["findings"]) == 1


def test_stamp_ids_rejects_empty_stdin() -> None:
    rc, _ = _run_stamp("   ")
    assert rc == 1


def test_stamp_ids_is_registered_as_a_subcommand() -> None:
    """`command_registry` is what the render-time permission/subcommand scan reads; an
    unregistered subcommand is invisible to it even when `main` accepts it."""
    from harness_maker import command_registry

    spec = command_registry.MODULES["codex_adapter"]
    assert "stamp-ids" in spec.subcommands
