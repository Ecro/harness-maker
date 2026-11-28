"""SPEC-change-card: the owner's short card at SPEC approval and at wrapup land."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from harness_maker import change_card, hm, i18n, wrapup_land
from harness_maker import worktree as wt
from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

SUMMARY = "Remind users of due items once a day so nothing slips."

SPEC_MD = f"""---
type: spec
task_slug: demo
status: draft
created: 2026-11-28
tags: [x]
test_framework: pytest
interview_rounds: 1
summary: {SUMMARY}
---

# SPEC — demo

## Intent

Long intent text the owner should not have to read.

## Non-Goals

- Push notifications to the phone.
- A settings page.

## Verification

| Scenario | Mode | AC |
|---|---|---|
| S1 | unit | AC-001 |
| S3 phone app shows the series | manual (open the app) | none |

## Open Questions

none

## Refinement Decisions

- **Storage:** optional `every` key on the v1 entry, expanded on read. Undo: minutes.
- **Clock:** UTC steps, so no DST drift. Undo: minutes.
"""


# AC-004 golden rows from SPEC-change-card.machine.yaml: (input, expected).
# Do not edit; `hm check` compares them with the SPEC.
AC_004_ROWS = [
    ({"locale": "ko"}, "검증함"),
    ({"locale": "en"}, "Verified"),
    ({"locale": "ja"}, "Verified"),
    ({"locale": None}, "Verified"),
]


def _ac(i: int, **kw: Any) -> dict[str, Any]:
    ac: dict[str, Any] = {
        "id": f"AC-{i:03d}",
        "title": kw.pop("title", f"criterion {i}"),
        "type": "mechanical",
        "executable_predicate": "x",
        "pending_test": False,
        "oracle_source": "golden",
        "oracle_evidence": "typed",
    }
    ac.update(kw)
    return ac


def _write_spec(root: Path, *, md: str = SPEC_MD, acs: list[dict[str, Any]] | None = None,
                irrs: list[dict[str, Any]] | None = None, slug: str = "demo") -> None:  # fmt: skip
    import yaml

    specs = root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / f"SPEC-{slug}.md").write_text(md, encoding="utf-8")
    model = {
        "schema_version": 3,
        "spec_slug": slug,
        "verification_tier": 1,
        "irreversible_decisions": irrs if irrs is not None else [],
        "ac": acs if acs is not None else [],
    }
    (specs / f"SPEC-{slug}.machine.yaml").write_text(
        yaml.safe_dump(model, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


IRRS = [
    {"id": "IRR-001", "decision": "Add optional every/count keys to the v1 save file",
     "category": "schema/file format/storage layout", "rationale": "phone app", "source": "spec"},
    {"id": "IRR-002", "decision": "New --every flag on remind add",
     "category": "public API/CLI contract", "rationale": "users", "source": "spec"},
]  # fmt: skip

S1_ACS = [
    _ac(1, title="series stored once"),
    _ac(2, title="weekly steps", type="parametric",
        golden_table=[{"input": {"every": "weekly", "count": 2}, "expected": ["d", "d+7"]}]),
    _ac(3, title="old files load unchanged"),
]  # fmt: skip


def test_ac_001_spec_card_order(tmp_path: Path) -> None:
    _write_spec(tmp_path, acs=S1_ACS, irrs=IRRS)
    card = change_card.spec_card(tmp_path, "demo", locale="en")
    anchors = [
        "SPEC-demo",
        SUMMARY,
        "AC-002",
        "every=weekly",
        "criteria (3)",
        "IRR-001 Add optional every/count keys to the v1 save file",
        "schema/file format/storage layout",
        "IRR-002",
        "Storage:",
        "Clock:",
        "Push notifications to the phone.",
        "Open questions: none",
        "specs/SPEC-demo.md",
    ]
    positions = [card.find(a) for a in anchors]
    assert -1 not in positions, (anchors, positions, card)
    assert positions == sorted(positions), card
    assert "Long intent text" not in card


def test_ac_002_spec_card_short_keeps_gating_items(tmp_path: Path) -> None:
    decisions = "\n".join(
        f"- **Decision {i}:** " + "a long reason that goes on " * 6 + f"end {i}." for i in range(20)
    )
    questions = ["Should a series of 52 weeks be the cap, or 104?", "Who owns the phone schema?"]
    md = (
        SPEC_MD.replace(
            "## Open Questions\n\nnone",
            "## Open Questions\n\n" + "\n".join(f"- {q}" for q in questions),
        )  # fmt: skip
        .replace(
            "- **Storage:** optional `every` key on the v1 entry, expanded on read. "
            "Undo: minutes.\n"
            "- **Clock:** UTC steps, so no DST drift. Undo: minutes.\n",
            decisions + "\n",
        )
        .replace("- A settings page.", "\n".join(f"- Non-goal number {i} " * 3 for i in range(8)))
    )
    acs = [_ac(i, title="a fairly long acceptance criterion title " * 2) for i in range(1, 13)]
    irrs = [
        {**IRRS[0], "id": f"IRR-{i:03d}", "decision": f"Decision {i} " + "with detail " * 8}
        for i in range(1, 5)
    ]
    _write_spec(tmp_path, md=md, acs=acs, irrs=irrs)
    card = change_card.spec_card(tmp_path, "demo", locale="en")
    irr_ids = [i["id"] for i in irrs]
    assert len(card) <= 1500, (len(card), card)
    assert all(i in card for i in irr_ids)
    assert all(q in card for q in questions)
    assert all(i["decision"].strip() in card for i in irrs), "an IRR is never trimmed"
    assert "+" in card
    assert "more" in card


# ── land card ─────────────────────────────────────────────────────────────────

MESSAGE = """feat(remind): recurring reminders

Why: owners forget weekly chores.

Understanding:
- storage: one row per reminder -> one row per series
- unknown: whether the phone app ignores unknown keys
- agent-decided: ADR-002 UTC steps
"""

REVIEW = """# REVIEW

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | remind/api.py:10 | bad error | accepted | - |
| F2 | P3 | tests/t.py:3 | weak test | accepted | - |
"""


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "init")
    return root


def _verdict(root: Path, slug: str = "demo", *, passed: bool = True) -> None:
    from harness_maker import check

    path = check.verdict_path(root)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    results = [{"cmd": c, "exit": 0} for c in ("ruff check .", "mypy src", "pytest -q")]
    record = {
        "slug": slug,
        "files": check.snapshot(root),
        "gates": {"ok": True, "source": "ci", "results": results},
        "line": {"exit": 0, "sections": {"ac": {"ok": True}}} if passed else None,
    }
    path.write_text(json.dumps(record), encoding="utf-8")


S3_ACS = [
    _ac(1, title="series stored once", test_ids=["tests/t.py::test_ac_001_a"]),
    _ac(2, title="weekly steps",
        test_ids=["tests/t.py::test_ac_002_a", "tests/t.py::test_ac_002_b"]),
    _ac(3, title="help text reads well", type="judgment", rubric_id="r",
        judgment_subject_paths=["remind/cli.py"], judgment_verdict="pass"),
]  # fmt: skip


def _section(card: str, label: str, nxt: str) -> str:
    start = card.index(label)
    end = card.index(nxt, start)
    return card[start:end]


def test_ac_003_land_card_verified_and_not(tmp_path: Path) -> None:
    root = _repo(tmp_path / "r")
    _write_spec(root, acs=S3_ACS, irrs=IRRS[:1])
    (root / "work-docs").mkdir()
    (root / "work-docs" / "REVIEW-demo-2026-11-28.md").write_text(REVIEW, encoding="utf-8")
    _verdict(root)
    card = change_card.land_card(root, "demo", MESSAGE, locale="en")
    verified = _section(card, "Verified:", "Not verified:")
    not_verified = _section(card, "Not verified:", "Changed assumptions:")
    verified_ok = (
        all(
            s in verified
            for s in (
                "hm check gates passed: 3 (ruff check ., mypy src, pytest -q)",
                "AC tests passed: 2 ACs, 3 tests",
                "Review: 2 findings, all disposed",
            )
        )
        and "AC-003" not in verified
    )
    not_verified_ok = "AC-003" in not_verified and "phone app shows the series" in not_verified
    tail = card[card.index("Changed assumptions:") :]
    understanding_ok = (
        "storage: one row per reminder -> one row per series"
        in _section(tail, "Changed", "Unknown:")
        and "whether the phone app ignores unknown keys"
        in _section(tail, "Unknown:", "Agent-decided:")
        and "ADR-002 UTC steps" in tail[tail.index("Agent-decided:") :]
        and card.index("feat(remind): recurring reminders") < card.index("Verified:")
    )  # fmt: skip

    bare = _repo(tmp_path / "bare")
    _write_spec(bare, acs=S3_ACS[:2])
    bare_card = change_card.land_card(bare, "demo", MESSAGE, locale="en")
    missing = _section(bare_card, "Not verified:", "Changed assumptions:")
    missing_ok = "hm check" in missing and "REVIEW" in missing
    assert verified_ok and not_verified_ok and understanding_ok and missing_ok, (  # noqa: PT018
        card,
        bare_card,
    )


def _not_verified(root: Path) -> str:
    card = change_card.land_card(root, "demo", MESSAGE, locale="en")
    assert "Verified:" in card
    return _section(card, "Not verified:", "Changed assumptions:")


def test_ac_003_land_card_never_claims_unchecked_work(tmp_path: Path) -> None:
    """Review F1/F2/F4/F5: a stale, failed or foreign record and an open REVIEW are not verified."""
    acs = [*S3_ACS[:2], _ac(4, title="parser edge", test_ids=["tests/t.py::x"], pending_test=True)]
    root = _repo(tmp_path / "r")
    _write_spec(root, acs=acs)
    (root / "work-docs").mkdir()
    review = root / "work-docs" / "REVIEW-demo-2026-11-28.md"
    review.write_text(REVIEW.replace("| accepted | - |\n", "| unresolved | - |\n", 1), "utf-8")
    _verdict(root, slug="other")
    foreign = _not_verified(root)
    assert "no hm check record for this task" in foreign
    assert "Review not closed" in foreign
    assert "F1" in foreign
    assert "AC-004 parser edge: no test bound" in foreign
    _verdict(root, passed=False)
    assert "the last hm check did not pass" in _not_verified(root)
    _verdict(root)
    (root / "remind.py").write_text("x = 1\n", encoding="utf-8")
    assert "code changed after the last hm check" in _not_verified(root)
    review.write_text(REVIEW.replace("| accepted | - |\n", "| bogus | - |\n", 1), "utf-8")
    (root / "remind.py").unlink()
    card = change_card.land_card(root, "demo", MESSAGE, locale="en")
    assert "all disposed" not in card
    assert "Review not closed" in _section(card, "Not verified:", "Changed assumptions:")
    review.write_text("# REVIEW\n\nno findings section\n", "utf-8")
    assert "Review: no findings" not in change_card.land_card(root, "demo", MESSAGE, locale="en")


@pytest.mark.parametrize(
    ("given", "expected"), AC_004_ROWS, ids=[f"AC-004-{i}" for i in range(len(AC_004_ROWS))]
)
def test_ac_004_labels_follow_harness_locale(
    given: dict[str, Any], expected: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path / "r")
    if given["locale"] is not None:
        (root / ".claude").mkdir()
        (root / ".claude" / "harness.yaml").write_text(
            f"---\ngenerated_by: harness-maker\n---\nlocale: {given['locale']}\n",
            encoding="utf-8",
        )
    _write_spec(root, acs=S3_ACS[:1])
    label = change_card.label("verified", i18n.resolve_locale(root))
    card = change_card.land_card(root, "demo", MESSAGE)
    assert expected in card
    assert change_card.main(["spec", "--root", str(root), "--slug", "demo"]) == 0
    printed = capsys.readouterr().out
    assert change_card.label("why", i18n.resolve_locale(root)) in printed
    assert label == expected


# ── wrapup_land ───────────────────────────────────────────────────────────────


def _land(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, broken: bool,
          capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any], str]:  # fmt: skip
    base = _repo(tmp_path / ("broken" if broken else "ok"))
    target = base / ".worktrees" / "demo"
    _git(base, "worktree", "add", "-b", "hm/demo", str(target))
    _write_spec(target, acs=S3_ACS[:1])
    msg = tmp_path / ("broken.txt" if broken else "ok.txt")
    msg.write_text(MESSAGE, encoding="utf-8")
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    monkeypatch.setattr(wt, "_cli_drain", lambda _a: 0)
    if broken:

        def boom(*_a: Any, **_k: Any) -> str:
            raise RuntimeError("card fault")

        monkeypatch.setattr(change_card, "land_card", boom)
    args = argparse.Namespace(
        worktree=str(target), base=str(base), slug="demo", message_file=str(msg),
        required=[], optional=["specs/"], allow_legacy_ref=False, manifest_only=False,
    )  # fmt: skip
    capsys.readouterr()
    code, receipt = wrapup_land.run(args)
    return code, receipt, capsys.readouterr().err


def test_ac_005_wrapup_land_carries_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ok_exit, ok_receipt, _ = _land(tmp_path, monkeypatch, broken=False, capsys=capsys)
    card = ok_receipt["steps"]["change_card"]
    ok_file = change_card.card_path(tmp_path / "ok", "demo")
    assert ok_file.read_text(encoding="utf-8") == f"{card}\n", "Step 8 Reads this file"
    stale = change_card.card_path(tmp_path / "broken", "demo")
    stale.parent.mkdir(parents=True)
    stale.write_text("an earlier land's card\n", encoding="utf-8")
    broken_exit, broken_receipt, stderr = _land(tmp_path, monkeypatch, broken=True, capsys=capsys)
    broken_card = broken_receipt["steps"]["change_card"]
    assert not change_card.card_path(tmp_path / "broken", "demo").exists()
    same = {k for k in ok_receipt["steps"] if k != "change_card"} == {
        k for k in broken_receipt["steps"] if k != "change_card"
    }
    assert same
    assert (
        broken_receipt["steps"]["understanding_block"] == ok_receipt["steps"]["understanding_block"]
    )
    assert isinstance(card, str) and broken_exit == ok_exit and broken_card is None and (  # noqa: PT018
        "[wrapup_land] change_card:" in stderr)  # fmt: skip


# ── stage text ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for locale in ("en", "ko"):
        base = tmp_path_factory.mktemp(f"card-{locale}")
        project = init_project(base / "proj")
        args = ("--autoloop", "--targets", "claude-code,codex", "--locale", locale,
                "--preset", "Production")  # fmt: skip
        proc = run_make(project, args, src=HEAD_SRC, home=base / "home")
        assert proc.returncode == 0, proc.stderr[-2000:]
        out[locale] = project
    return out


def _step(text: str, heading: str) -> str:
    start = text.index(f"## {heading}")
    nxt = text.find("\n## ", start + 1)
    return text[start : nxt if nxt != -1 else len(text)]


_PATHS = {
    "claude": ".claude/commands/hm/{}.md",
    "codex": ".agents/skills/hm-{}/SKILL.md",
}


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_ac_006_stages_show_the_card(renders: dict[str, Path], runtime: str) -> None:
    def read(locale: str, stage: str) -> str:
        return (renders[locale] / _PATHS[runtime].format(stage)).read_text(encoding="utf-8")

    spec_en, wrap_en = read("en", "spec"), read("en", "wrapup")
    spec_ko, wrap_ko = read("ko", "spec"), read("ko", "wrapup")
    step2 = _step(spec_en, "Step 2")
    spec_ok = (
        "hm change_card spec --slug <slug>" in step2
        and "approval question" in step2
        and "(Steps 3–3.5) first, then ask it" in step2
        and "rerun after any SPEC edit (the validator's too, before the stamp)" in step2
        and "output as your message, verbatim" in step2
        and "add no other summary" in step2
    )
    close = _step(wrap_en, "Step 8")
    wrapup_ok = (
        "`steps.change_card`" in close
        and "Read `.claude/observability/change-card-<slug>.txt`" in close
        and "no other summary" in close
    )
    fallback_ok = (
        "`steps.understanding_block` verbatim" in close
        and close.index("`steps.change_card`") < close.index("`steps.understanding_block`")
        and "if that file is missing" in close
    )
    sentence = "free-text lines in `ko`"
    locale_ok = (
        sentence in _step(spec_ko, "Step 2")
        and sentence in _step(wrap_ko, "Step 8")
        and "free-text lines in" not in step2 + close
    )
    dispatchable = hm._DISPATCHABLE
    assert spec_ok and wrapup_ok and fallback_ok and locale_ok and "change_card" in dispatchable  # noqa: PT018


# ── saga bench ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def saga() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "saga_bench.py"
    spec = importlib.util.spec_from_file_location("saga_bench_card", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ac_007_saga_counts_messages_only(saga: ModuleType) -> None:
    session = {
        "turns": [{"kind": "task", "message": "a" * 10, "sim": {"reply": None}},
                  {"kind": "reply", "message": "b" * 20, "sim": {"reply": None}}],
        "hidden": {"t": "passed"}, "interrupted": False,
    }  # fmt: skip
    read_without_doc = saga.attention(session)["read_chars"]
    read_with_doc = saga.attention({**session, "doc_chars": 500})["read_chars"]
    rows = [
        {"arm": "hm", "status": "ok", "escaped": [],
         "sessions": {"S1": {**session, "doc_chars": 500}, "S2": {**session, "doc_chars": 300}}},
    ]  # fmt: skip
    summary = saga.owner_summary(rows)
    expected_spec = 400.0
    assert (  # noqa: PT018
        read_with_doc == read_without_doc == 30 and summary["hm"]["spec_per_ship"] == expected_spec
    )
