"""Phase 4: the delegated wrapup's OUTPUT contract (ADR-012).

A complete brief does not imply a complete wrapup. The existing visibility
mechanism for under-promotion is a single prose line the agent prints
(`promotion evaluated: N candidates, M promoted`), and delegation puts that line
behind a summarising main loop — which would happily relay it whether the agent
printed it, printed `N=0`, or printed nothing.

So the receipt is machine-shaped and every claim in it is checked against
observable state. A test that only round-trips the schema would leave exactly the
hole this exists to close.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from harness_maker import wrapup_receipt as wr


def _memory(
    base: Path, *, wiki: list[str] | None = None, failures: list[str] | None = None
) -> None:
    md = base / ".claude" / "memory"
    md.mkdir(parents=True, exist_ok=True)
    wiki, failures = wiki or [], failures or []
    (md / "wiki.md").write_text(
        "".join(f"## [wiki:architecture] {s} | 2026-07-26\n\nbody\n\n" for s in wiki),
        encoding="utf-8",
    )
    (md / "failures.md").write_text(
        "".join(f"## [fail:test] {s} | 2026-07-26 | count:1\n\nbody\n\n" for s in failures),
        encoding="utf-8",
    )


def _receipt(**overrides: object) -> wr.WrapupReceipt:
    fields: dict[str, object] = {
        "schema_version": wr.SCHEMA_VERSION,
        "stage": "wrapup",
        "wiki_slugs": (),
        "failure_slugs": (),
        "promotion_candidates": 0,
        "promoted_slugs": (),
        "promotion_skips": (),
        "documents_updated": (),
    }
    fields.update(overrides)
    return wr.WrapupReceipt.model_validate(fields)


# ------------------------------------------------------------------ positive control


def test_a_receipt_whose_claims_all_hold_reconciles_clean(tmp_path: Path) -> None:
    """Positive control: without it, every mismatch test below passes against a
    reconciler that reports `ok=False` unconditionally."""
    _memory(tmp_path, wiki=["span-ledger-design"], failures=["stale-snapshot-memory"])
    (tmp_path / "CHANGELOG.md").write_text("x\n", encoding="utf-8")

    result = wr.reconcile(
        _receipt(
            wiki_slugs=("span-ledger-design",),
            failure_slugs=("stale-snapshot-memory",),
            documents_updated=("CHANGELOG.md",),
        ),
        base_root=tmp_path,
    )

    assert result.ok is True
    assert result.mismatches == ()
    assert result.checked == 3


# ------------------------------------------------------------------ claim vs reality


def test_a_claimed_wiki_slug_that_is_not_in_the_tier_file_is_a_mismatch(tmp_path: Path) -> None:
    """The core of ADR-012: the agent says it wrote an entry, the file says otherwise.
    Trusting the prose is precisely what this replaces."""
    _memory(tmp_path, wiki=["something-else"])

    result = wr.reconcile(_receipt(wiki_slugs=("never-written",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["wiki-missing"]
    assert "never-written" in result.mismatches[0].detail


def test_a_claimed_failure_slug_that_is_not_in_the_tier_file_is_a_mismatch(
    tmp_path: Path,
) -> None:
    _memory(tmp_path, failures=["something-else"])

    result = wr.reconcile(_receipt(failure_slugs=("never-written",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["failure-missing"]


def test_a_claimed_document_that_does_not_exist_is_a_mismatch(tmp_path: Path) -> None:
    _memory(tmp_path)

    result = wr.reconcile(_receipt(documents_updated=("docs/NOPE.md",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["document-missing"]


def test_absent_tier_files_make_every_claim_a_mismatch_rather_than_a_pass(
    tmp_path: Path,
) -> None:
    """The absent case, and the one that silently inverts: a reader that treats a
    missing `wiki.md` as "nothing to check" turns the worst outcome — the agent wrote
    nothing at all — into a clean reconciliation."""
    result = wr.reconcile(
        _receipt(wiki_slugs=("a",), failure_slugs=("b",)),
        base_root=tmp_path,
    )

    assert result.ok is False
    assert {m.kind for m in result.mismatches} == {"wiki-missing", "failure-missing"}


def test_a_slug_appearing_only_in_the_other_tier_file_does_not_count(tmp_path: Path) -> None:
    """Cross-file leakage: grepping both files for any slug would let a wiki entry
    satisfy a failure claim."""
    _memory(tmp_path, wiki=["shared-name"], failures=[])

    result = wr.reconcile(_receipt(failure_slugs=("shared-name",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["failure-missing"]


def test_a_slug_that_is_only_a_substring_of_a_real_entry_does_not_count(
    tmp_path: Path,
) -> None:
    """Substring matching would let `span` satisfy a claim about `span-ledger-design`
    — and, worse, make a truncated slug reconcile against the entry it truncated."""
    _memory(tmp_path, wiki=["span-ledger-design"])

    result = wr.reconcile(_receipt(wiki_slugs=("span",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["wiki-missing"]


def test_reconciliation_resolves_the_tier_files_from_the_base_even_inside_a_worktree(
    tmp_path: Path,
) -> None:
    """Memory tiers live at the base; a worktree copy is ephemeral. Reading the
    worktree path would reconcile against a file `task-land` is about to delete."""
    base = tmp_path / "repo"
    _memory(base, wiki=["written-at-base"])
    wt = base / ".worktrees" / "my-task"
    wt.mkdir(parents=True)

    result = wr.reconcile(_receipt(wiki_slugs=("written-at-base",)), base_root=wt)

    assert result.ok is True


# ------------------------------------------------------------------ promotion arithmetic


def test_promotion_counts_that_do_not_add_up_are_a_mismatch(tmp_path: Path) -> None:
    """The anti-fabrication check. `candidates: 5, promoted: 1` with no skip reasons
    is the shape a summarising main loop produces when it invents a plausible line —
    and it is arithmetically impossible for an agent that actually evaluated five."""
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(promotion_candidates=5, promoted_slugs=("a",)),
        base_root=tmp_path,
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["promotion-arithmetic"]


def test_promotion_counts_that_add_up_reconcile(tmp_path: Path) -> None:
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(
            promotion_candidates=3,
            promoted_slugs=("a",),
            promotion_skips=(
                wr.PromotionSkip(slug="b", reason="project-local"),
                wr.PromotionSkip(slug="c", reason="already promoted"),
            ),
        ),
        base_root=tmp_path,
    )

    assert result.ok is True


def test_promoting_more_than_were_evaluated_is_a_mismatch(tmp_path: Path) -> None:
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("a", "b")),
        base_root=tmp_path,
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["promotion-arithmetic"]


def test_zero_candidates_with_nothing_promoted_is_a_valid_receipt(tmp_path: Path) -> None:
    """ "Nothing was durable this round" is a legitimate wrapup outcome. Flagging it
    would push the agent to invent a promotion to make the receipt clean — exactly the
    synthetic-note pressure CLAUDE.md's no-count-gate rule exists to avoid."""
    _memory(tmp_path)

    result = wr.reconcile(_receipt(promotion_candidates=0), base_root=tmp_path)

    assert result.ok is True


def _skip_payload(reason: str) -> str:
    return json.dumps(
        {
            "schema_version": wr.SCHEMA_VERSION,
            "stage": "wrapup",
            "promotion_candidates": 1,
            "promotion_skips": [{"slug": "b", "reason": reason}],
        }
    )


def test_a_skip_without_a_reason_is_rejected() -> None:
    """ "Skipped" with no reason is unauditable — it is the field that makes
    under-promotion diagnosable rather than merely visible."""
    receipt, error = wr.parse_receipt(_skip_payload("  "))

    assert receipt is None
    assert error


def test_a_skip_with_a_reason_parses() -> None:
    """Positive control for the test above: a parser that rejects any payload
    containing `promotion_skips` at all would satisfy it."""
    receipt, error = wr.parse_receipt(_skip_payload("project-local"))

    assert error == ""
    assert receipt is not None
    assert receipt.promotion_skips[0].reason == "project-local"


# ------------------------------------------------------------------ vault verification


def _vault(tmp_path: Path, *notes: str) -> Path:
    """A vault with its `second_brain.folders` allowlist populated.

    Every caller must pass `vault_folders=["notes"]`: an UNCONFIGURED folder list now
    refuses every claim (review R2-04), because `promote_note` refuses to write in that
    config, so nothing this harness produced can be in the vault.
    """
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True, exist_ok=True)
    for note in notes:
        (vault / "notes" / note).write_text("x\n", encoding="utf-8")
    return vault


def test_a_promoted_slug_is_verified_against_the_vault_when_one_is_given(
    tmp_path: Path,
) -> None:
    """The vault holds an unrelated note too, so passing requires resolving the SLUG
    rather than observing that the directory is non-empty."""
    _memory(tmp_path)
    vault = _vault(tmp_path, "decision-span-ledger.md", "preference-editor-theme.md")

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("span-ledger",)),
        base_root=tmp_path,
        vault_root=vault,
        vault_folders=["notes"],
    )

    assert result.ok is True


def test_a_promoted_slug_absent_from_a_populated_vault_is_a_mismatch(tmp_path: Path) -> None:
    """The realistic fabrication shape: the agent promoted something in an earlier
    round, so the vault is NOT empty, and this round's claim names a note that was
    never written. An emptiness check reconciles this clean."""
    _memory(tmp_path)
    vault = _vault(tmp_path, "decision-something-else.md")

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("span-ledger",)),
        base_root=tmp_path,
        vault_root=vault,
        vault_folders=["notes"],
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["promotion-missing"]


def test_a_promoted_slug_that_is_only_a_substring_of_a_vault_note_is_a_mismatch(
    tmp_path: Path,
) -> None:
    """Same leak the tier-file side already closes: `span` must not be satisfied by
    `decision-span-ledger.md`, or a truncated slug reconciles against the note it
    truncated."""
    _memory(tmp_path)
    vault = _vault(tmp_path, "decision-span-ledger.md")

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("span",)),
        base_root=tmp_path,
        vault_root=vault,
        vault_folders=["notes"],
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["promotion-missing"]


def test_an_empty_vault_makes_every_promotion_claim_a_mismatch(tmp_path: Path) -> None:
    """The absent case, kept separate from the discriminating tests above."""
    _memory(tmp_path)
    vault = _vault(tmp_path)

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("span-ledger",)),
        base_root=tmp_path,
        vault_root=vault,
        vault_folders=["notes"],
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["promotion-missing"]


def test_without_a_vault_path_promotions_are_reported_unverified_not_passed(
    tmp_path: Path,
) -> None:
    """Second Brain is optional and lives outside the repo. Counting an uncheckable
    claim as verified would let the one number CLAUDE.md relies on go unchecked while
    the report says `ok`."""
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("span-ledger",)),
        base_root=tmp_path,
    )

    assert result.ok is True  # not a failure — it is simply not checkable
    assert result.unverified == 1


# ------------------------------------------------------------------ parsing


def test_a_well_formed_receipt_parses() -> None:
    receipt, error = wr.parse_receipt(
        json.dumps(
            {
                "schema_version": wr.SCHEMA_VERSION,
                "stage": "wrapup",
                "wiki_slugs": ["a"],
                "promotion_candidates": 1,
                "promoted_slugs": ["a"],
            }
        )
    )

    assert error == ""
    assert receipt is not None
    assert receipt.wiki_slugs == ("a",)


def test_a_receipt_wrapped_in_a_markdown_fence_still_parses() -> None:
    """Agents fence JSON by reflex. Failing on the fence would degrade every delegated
    wrapup for a formatting habit, and the fallback is the inline body — so the
    feature would appear not to work."""
    payload = json.dumps({"schema_version": wr.SCHEMA_VERSION, "stage": "wrapup"})
    receipt, error = wr.parse_receipt(f"here you go:\n```json\n{payload}\n```\n")

    assert error == ""
    assert receipt is not None


def test_prose_with_no_json_at_all_fails_closed_with_a_reason() -> None:
    """The delegated body returning prose is exactly the ADR-012 failure. It must be
    loud, not coerced into an empty receipt that reconciles clean."""
    receipt, error = wr.parse_receipt("I wrapped everything up nicely!")

    assert receipt is None
    assert error


def test_two_json_payloads_are_rejected_rather_than_guessed_between() -> None:
    """Fail-closed on ambiguity, mirroring `codex_adapter.extract_antigravity_payload`:
    picking one would silently reconcile against whichever the parser happened to
    prefer."""
    one = json.dumps({"schema_version": wr.SCHEMA_VERSION, "stage": "wrapup"})
    two = json.dumps({"schema_version": wr.SCHEMA_VERSION, "stage": "verify"})
    receipt, error = wr.parse_receipt(f"```json\n{one}\n```\nand\n```json\n{two}\n```")

    assert receipt is None
    assert error


def test_a_receipt_from_a_future_schema_version_is_rejected() -> None:
    """Reconciling a shape we do not understand would check the fields we recognise
    and silently ignore any new claim."""
    receipt, error = wr.parse_receipt(
        json.dumps({"schema_version": wr.SCHEMA_VERSION + 1, "stage": "wrapup"})
    )

    assert receipt is None
    assert error


# ------------------------------------------------- review round 2 (F-04, M-05, M-11)


def test_an_absolute_claimed_path_is_rejected_rather_than_probed(tmp_path: Path) -> None:
    """F-04. `Path("/base") / "/etc/hostname"` is `/etc/hostname`, so an unvalidated
    join let a delegate satisfy reconciliation with any existing file on the machine —
    after which the verify template adopts the receipt's verdict."""
    _memory(tmp_path)

    result = wr.reconcile(_receipt(documents_updated=("/etc/hostname",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["document-escapes-root"]


def test_a_dot_dot_claimed_path_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("x\n", encoding="utf-8")
    _memory(tmp_path)

    result = wr.reconcile(_receipt(documents_updated=("../outside.md",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["document-escapes-root"]


def test_a_claimed_directory_does_not_satisfy_a_document_claim(tmp_path: Path) -> None:
    """`.exists()` accepted a directory; `is_file()` is what the claim means."""
    _memory(tmp_path)
    (tmp_path / "docs").mkdir()

    result = wr.reconcile(_receipt(documents_updated=("docs",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["document-missing"]


def test_documents_resolve_against_the_worktree_when_one_is_given(tmp_path: Path) -> None:
    """M-05. The delegate is told to write only inside the worktree, and
    `.claude/observability/` is gitignored churn that exists ONLY there — so resolving
    document claims at base false-failed every delegated run."""
    base = tmp_path / "repo"
    _memory(base)
    wt = base / ".worktrees" / "my-task"
    (wt / "work-docs").mkdir(parents=True)
    (wt / "work-docs" / "PLAN-my-task.md").write_text("x\n", encoding="utf-8")

    result = wr.reconcile(
        _receipt(documents_updated=("work-docs/PLAN-my-task.md",)),
        base_root=wt,
        worktree_root=wt,
    )

    assert result.ok is True


def test_memory_tiers_still_resolve_at_base_even_with_a_worktree_root(tmp_path: Path) -> None:
    """Negative control for the split: tiers are shared project state committed by
    wrapup, so they must NOT follow the document root into the worktree."""
    base = tmp_path / "repo"
    _memory(base, wiki=["written-at-base"])
    wt = base / ".worktrees" / "my-task"
    wt.mkdir(parents=True)

    result = wr.reconcile(_receipt(wiki_slugs=("written-at-base",)), base_root=wt, worktree_root=wt)

    assert result.ok is True


def test_a_receipt_for_another_stage_is_rejected_when_a_stage_is_expected(
    tmp_path: Path,
) -> None:
    """F-05. `stage` was a free string nothing compared against, so a wrapup receipt
    could be reconciled as a verify one."""
    _memory(tmp_path)

    result = wr.reconcile(_receipt(), base_root=tmp_path, expected_stage="verify")

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["stage-mismatch"]


def test_duplicate_promoted_slugs_do_not_satisfy_the_arithmetic(tmp_path: Path) -> None:
    """M-11. `promoted=("a","a")` with `candidates=2` passed the count check while
    only one thing was ever evaluated."""
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(promotion_candidates=2, promoted_slugs=("a", "a")), base_root=tmp_path
    )

    assert result.ok is False
    assert "promotion-duplicate" in [m.kind for m in result.mismatches]


def test_a_slug_both_promoted_and_skipped_is_rejected(tmp_path: Path) -> None:
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(
            promotion_candidates=2,
            promoted_slugs=("a",),
            promotion_skips=(wr.PromotionSkip(slug="a", reason="also skipped?"),),
        ),
        base_root=tmp_path,
    )

    assert result.ok is False
    assert "promotion-duplicate" in [m.kind for m in result.mismatches]


def test_a_vault_note_without_a_known_type_prefix_does_not_satisfy_a_claim(
    tmp_path: Path,
) -> None:
    """M-02. `stem.split("-", 1)[1]` turned a user's own `my-notes.md` into slug
    `notes`, so a promotion claim could be satisfied by a file the harness never
    wrote — anywhere in a personal Obsidian vault."""
    _memory(tmp_path)
    vault = _vault(tmp_path, "my-notes.md")

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("notes",)),
        base_root=tmp_path,
        vault_root=vault,
        vault_folders=["notes"],
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["promotion-missing"]


def test_the_vault_walk_honours_the_configured_folder_allowlist(tmp_path: Path) -> None:
    """The allowlist a prior security review introduced to keep the harness out of the
    rest of a personal vault. A note outside it must not satisfy a claim."""
    _memory(tmp_path)
    vault = tmp_path / "vault"
    (vault / "harness").mkdir(parents=True)
    (vault / "personal").mkdir(parents=True)
    (vault / "personal" / "decision-private.md").write_text("x\n", encoding="utf-8")

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("private",)),
        base_root=tmp_path,
        vault_root=vault,
        vault_folders=["harness"],
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["promotion-missing"]


def test_a_second_payload_is_detected_even_when_the_first_is_fenced() -> None:
    """M-06. The fenced branch short-circuited, so a fenced payload plus an unfenced
    one bypassed the "refuse if more than one" promise entirely."""
    one = json.dumps({"schema_version": wr.SCHEMA_VERSION, "stage": "wrapup"})
    two = json.dumps({"schema_version": wr.SCHEMA_VERSION, "stage": "verify"})
    receipt, error = wr.parse_receipt(f"```json\n{one}\n```\nalso: {two}")

    assert receipt is None
    assert "2 JSON objects" in error


def test_a_brace_inside_a_string_does_not_split_the_payload() -> None:
    """M-08 / M-12. Character-level brace counting mis-split `{"a": "}"}`."""
    receipt, error = wr.parse_receipt(
        json.dumps(
            {
                "schema_version": wr.SCHEMA_VERSION,
                "stage": "wrapup",
                "documents_updated": ["weird}name.md"],
            }
        )
    )

    assert error == ""
    assert receipt is not None
    assert receipt.documents_updated == ("weird}name.md",)


# ------------------------------------------------- review round 3 (R2-02, R2-03, R2-04)


def test_a_symlink_escape_is_rejected(tmp_path: Path) -> None:
    """R2-03. The two F-04 tests supply `/etc/hostname` and `../outside.md` — BOTH
    return at the pure-string guard, so `resolve()` + `is_relative_to` (the only
    defence against a symlink, which is neither absolute nor `..`-bearing) was never
    executed by any test. A refactor deleting them as "redundant with the string
    checks" would have left the suite fully green while reopening F-04.
    """
    base = tmp_path / "repo"
    _memory(base)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("x\n", encoding="utf-8")
    (base / "link").symlink_to(outside, target_is_directory=True)

    result = wr.reconcile(_receipt(documents_updated=("link/secret.md",)), base_root=base)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["document-escapes-root"]


def test_a_symlink_that_stays_inside_the_root_is_accepted(tmp_path: Path) -> None:
    """Negative control: the fix must reject ESCAPES, not symlinks as such."""
    base = tmp_path / "repo"
    _memory(base)
    (base / "real").mkdir()
    (base / "real" / "doc.md").write_text("x\n", encoding="utf-8")
    (base / "link").symlink_to(base / "real", target_is_directory=True)

    result = wr.reconcile(_receipt(documents_updated=("link/doc.md",)), base_root=base)

    assert result.ok is True


def test_an_embedded_nul_does_not_escape_the_never_raises_contract(tmp_path: Path) -> None:
    """R2-05. `os.lstat` raises ValueError, not OSError, on an embedded NUL — and the
    string survives pydantic's strict `str`. `reconcile` promises never to raise."""
    _memory(tmp_path)

    result = wr.reconcile(_receipt(documents_updated=("a\x00b.md",)), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["document-escapes-root"]


def test_every_second_brain_note_type_can_satisfy_a_promotion_claim(tmp_path: Path) -> None:
    """R2-02. The hand-copied allowlist omitted `journal`, which `wrapup.md.j2` Step 5.6
    explicitly offers — so a truthful journal promotion reconciled as `promotion-missing`
    and the template told the main loop to treat an honest claim as fabricated.

    Parametrised over the ENUM, so a seventh type added later fails here rather than
    silently becoming unpromotable.
    """
    from harness_maker.models import SecondBrainNoteType

    _memory(tmp_path)
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    for note_type in SecondBrainNoteType:
        (vault / "notes" / f"{note_type.value}-slug-{note_type.value}.md").write_text(
            "x\n", encoding="utf-8"
        )

    for note_type in SecondBrainNoteType:
        result = wr.reconcile(
            _receipt(promotion_candidates=1, promoted_slugs=(f"slug-{note_type.value}",)),
            base_root=tmp_path,
            vault_root=vault,
            vault_folders=["notes"],
        )
        assert result.ok is True, f"{note_type.value} could not satisfy a promotion claim"


def test_an_unconfigured_folder_list_refuses_every_promotion_claim(tmp_path: Path) -> None:
    """R2-04. Falling back to `[vault_root]` when no folders are configured re-opened
    the unbounded walk M-02 was raised about. `promote_note` refuses to WRITE in that
    config, so nothing this harness produced can be in the vault — the honest answer is
    "no slugs", not "the whole vault"."""
    _memory(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "decision-anything.md").write_text("x\n", encoding="utf-8")

    result = wr.reconcile(
        _receipt(promotion_candidates=1, promoted_slugs=("anything",)),
        base_root=tmp_path,
        vault_root=vault,
        vault_folders=None,
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["promotion-missing"]


# ---------------------------------------------- config-shape → verdict (round 5, P1)


def _harness_yaml(base: Path, vault: Path, *, legacy_key: bool) -> None:
    """A real `second_brain` block, optionally carrying the retired key.

    `second_brain._load_config` pops `_DEPRECATED_FIELDS` before validating precisely
    because consuming projects' on-disk harness.yaml still carry `trusted_allowlist`,
    and `promote_note` therefore accepts and WRITES under such a config.
    """
    # The writable folder MUST contain `project_id` as a path segment, or
    # `SecondBrainConfig`'s own validator rejects the block for that reason instead —
    # which would make the legacy-key case indistinguishable from the clean one and
    # this whole parametrisation vacuous. (It did, on the first draft of this test.)
    block = {
        "enabled": True,
        "vault_path": str(vault),
        "project_id": "demo",
        "folders": [{"path": "demo/notes", "write": True}],
    }
    if legacy_key:
        block["trusted_allowlist"] = ["anything"]
    (base / ".claude").mkdir(parents=True, exist_ok=True)
    (base / ".claude" / "harness.yaml").write_text(
        yaml.safe_dump({"second_brain": block}), encoding="utf-8"
    )


@pytest.mark.parametrize("legacy_key", [False, True], ids=["clean-config", "legacy-key"])
def test_a_truthful_promotion_is_never_reported_as_fabricated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], legacy_key: bool
) -> None:
    """A config-SHAPE problem must not become an accusation that the agent lied.

    `_configured_vault` reads the raw dict; `_configured_vault_folders` validates it
    with `extra="forbid"`. When only the strict one failed, the vault looked configured
    while the folder allowlist came back empty — so `_vault_slugs` returned nothing and
    every truthful promotion reconciled as `promotion-missing`, telling the main loop
    to go fix claims that were already on disk.

    The `legacy-key` case is the one that regressed; `clean-config` is the positive
    control that proves the assertion is not vacuous.
    """
    vault = tmp_path / "vault"
    (vault / "demo" / "notes").mkdir(parents=True)
    (vault / "demo" / "notes" / "decision-span-ledger.md").write_text("x\n", encoding="utf-8")
    _harness_yaml(tmp_path, vault, legacy_key=legacy_key)
    receipt = tmp_path / "r.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": wr.SCHEMA_VERSION,
                "stage": "wrapup",
                "promotion_candidates": 1,
                "promoted_slugs": ["span-ledger"],
            }
        ),
        encoding="utf-8",
    )

    rc = wr.main(
        [
            "--root",
            str(tmp_path),
            "--stage",
            "wrapup",
            "--worktree",
            str(tmp_path),
            "--receipt-file",
            str(receipt),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0, payload
    result = payload["result"]
    assert payload["status"] == "ok"
    kinds = [m["kind"] for m in result["mismatches"]]
    assert "promotion-missing" not in kinds, payload
    # Not merely "not accused" — VERIFIED. The fail-safe alone satisfies the assertions
    # above by reporting the claim as `unverified`, so stopping there leaves the
    # legacy-key strip untested. Measured: with the strip removed and only the
    # fail-safe in place, the assertions above still passed and these two did not.
    assert result["unverified"] == 0, payload
    assert result["checked"] >= 1, payload
    assert payload["vault_checked"] is not None, payload


def test_an_unparseable_second_brain_block_reports_unverified_not_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The fail-safe half, which the legacy-key test above does NOT cover.

    Stripping the retired keys fixes the ONE shape we know about. Any other shape the
    strict validator rejects — a forward-compat key, a folder that fails the
    project-namespacing rule — still leaves `_configured_vault` returning a path while
    `_configured_vault_folders` returns None, and the vault walk then finds nothing.
    The verdict for "could not read the config" must be `unverified`, which vouches for
    nothing, and never `promotion-missing`, which asserts the agent made the claim up.
    """
    vault = tmp_path / "vault"
    (vault / "demo" / "notes").mkdir(parents=True)
    (base_yaml := tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    (base_yaml / "harness.yaml").write_text(
        yaml.safe_dump(
            {
                "second_brain": {
                    "enabled": True,
                    "vault_path": str(vault),
                    "project_id": "demo",
                    "folders": [{"path": "demo/notes", "write": True}],
                    "a_key_from_a_future_version": True,
                }
            }
        ),
        encoding="utf-8",
    )
    receipt = tmp_path / "r.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": wr.SCHEMA_VERSION,
                "stage": "wrapup",
                "promotion_candidates": 1,
                "promoted_slugs": ["span-ledger"],
            }
        ),
        encoding="utf-8",
    )

    rc = wr.main(
        [
            "--root",
            str(tmp_path),
            "--stage",
            "wrapup",
            "--worktree",
            str(tmp_path),
            "--receipt-file",
            str(receipt),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    result = payload["result"]

    assert rc == 0, payload
    assert [m["kind"] for m in result["mismatches"]] == [], payload
    assert result["unverified"] == 1, payload
    assert payload["vault_checked"] is None, payload
