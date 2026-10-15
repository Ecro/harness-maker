"""Fixture builder for SPEC-hm-light-lane-s3a, shared by the e7dd6648 capture and the new tests.

One builder for both sides is AC-004's precondition: the differential compares the e7dd6648
boundary with the new one on fixtures built by the same code, so only the module under test
differs. It therefore uses only APIs that exist at e7dd6648 (`spec_machine.approve`,
`autopilot.write` / `narrow`, `autopilot_ledger.append_event`, `verification_cache`), and it
is run against that tree by `tests/fixtures/light_lane_s3a/capture_e7dd6648.py.txt`.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

SLUG = "demo"
RECORD_DATE = "2026-10-15"
OLDER_DATE = "2026-10-14"
DEFAULT_PIPELINE = ("research", "spec", "execute", "review", "verify", "wrapup")
PIPELINES: dict[str, tuple[str, ...]] = {
    "default": DEFAULT_PIPELINE,
    # `narrow --until review` on the default pipeline.
    "narrowed_review": DEFAULT_PIPELINE,
    "custom": ("execute", "verify", "wrapup"),
}
#: AC-005's extra shapes. Kept apart from PIPELINES, which is AC-004's captured domain.
EXTRA_PIPELINES: dict[str, tuple[str, ...]] = {
    "no_wrapup": ("research", "spec", "execute", "review", "verify"),
    "from_spec": ("spec", "execute", "review", "verify", "wrapup"),
}
#: Volatile values masked before a comparison: wall-clock stamps and the per-project uuid.
MASKED_ROW_KEYS = ("ts", "elapsed_s")
MASKED_MARKER_KEYS = ("created_at", "last_seen", "session_uuid")

MACHINE_DOC: dict[str, Any] = {
    "schema_version": 3,
    "spec_slug": SLUG,
    "verification_tier": 1,
    "irreversible_decisions": [],
    "ac": [
        {
            "id": "AC-001",
            "title": "the thing works",
            "type": "mechanical",
            "executable_predicate": "result == 1",
            "oracle_source": "golden",
            "oracle_evidence": "hand-written",
            "pending_test": True,
        }
    ],
}


@dataclass(frozen=True)
class Case:
    """One boundary input: the (lane, record) pair plus the boundary's own arguments."""

    lane: str
    record: str
    current: str
    level: str = "auto_safe"
    gate: str | None = None
    pipeline: str = "default"
    slug: bool = True

    @property
    def key(self) -> str:
        gate = self.gate or "absent"
        slug = "" if self.slug else "/no-slug"
        return f"{self.lane}+{self.record}/{self.current}/{self.level}/{gate}/{self.pipeline}{slug}"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, timeout=30)


def init_repo(root: Path) -> None:
    """A committed repo whose harness churn is ignored, as `_ensure_harness_gitignore` leaves it."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Fixture User")
    _git(root, "config", "user.email", "fixture@example.invalid")
    (root / ".gitignore").write_text(".claude/*\n.worktrees/\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def write_spec(
    checkout: Path,
    lane: str,
    *,
    irreversible: list[dict[str, str]] | None = None,
    slug: str = SLUG,
) -> None:
    """Write `SPEC-<slug>.md` + machine yaml for one lane kind, approving where the kind says."""
    from harness_maker import spec_machine

    specs = checkout / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    if lane == "none":
        return
    md = specs / f"SPEC-{slug}.md"
    yml = specs / f"SPEC-{slug}.machine.yaml"
    lane_line = {
        "full": "lane: full\n",
        "absent": "",
        "Light": "lane: Light\n",
        "light_space": "lane: 'light '\n",
        "light_true": "lane: true\n",
        "unparseable": "lane: [light\n",
    }.get(lane, "lane: light\n")
    md.write_text(f"---\ntype: spec\ntask_slug: {slug}\n{lane_line}---\n# SPEC\n", encoding="utf-8")
    if lane == "md_only":
        return
    doc = copy.deepcopy(MACHINE_DOC)
    doc["spec_slug"] = slug
    if irreversible is not None:
        doc["irreversible_decisions"] = irreversible
    if lane == "legacy":
        doc["schema_version"] = 2
        doc.pop("irreversible_decisions")
    yml.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    if lane in ("untrusted", "legacy"):
        return
    if lane == "exempt":
        spec_machine.approve(yml, exempt=True)
        return
    spec_machine.approve(yml)
    if lane == "invalid":
        raw = yaml.safe_load(yml.read_text(encoding="utf-8"))
        raw["ac"][0]["title"] = "edited after approval"
        yml.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def record_text(
    *,
    slug: str = SLUG,
    task_slug: str | None = None,
    status: str | None = "PASSED",
    review_kind: str | None = "light-check",
    computed_at: str | None,
    spec_requirement: str = "pass",
) -> str:
    """A REVIEW-shaped record; `review_kind=None` is a real review."""
    fm: dict[str, Any] = {"type": "review"}
    if review_kind is not None:
        fm["review_kind"] = review_kind
    fm["task_slug"] = task_slug or slug
    if status is not None:
        fm["status"] = status
    fm["created"] = RECORD_DATE
    verdict: dict[str, Any] = {
        "result": "clean",
        "scope_violations": [],
        "scenario_misses": [],
        "task_slug": task_slug or slug,
    }
    if computed_at is not None:
        verdict["computed_at"] = computed_at
    fm["drift_verdict"] = verdict
    if review_kind is not None:
        fm["checks"] = {
            "mechanical": "n-a",
            "regression": "pass",
            "security": "pass",
            "spec_requirement": spec_requirement,
            "structural": "not-run",
        }
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n# Review\n"


def write_record(checkout: Path, kind: str, *, marker_created: datetime) -> None:
    """Write the REVIEW record(s) one record kind names, under `<checkout>/work-docs/`."""
    docs = checkout / "work-docs"
    docs.mkdir(parents=True, exist_ok=True)
    after = (marker_created + timedelta(minutes=5)).isoformat()
    before = (marker_created - timedelta(hours=1)).isoformat()
    name = f"REVIEW-{SLUG}-{RECORD_DATE}.md"
    older = f"REVIEW-{SLUG}-{OLDER_DATE}.md"
    real = record_text(status="CHANGES_REQUESTED", review_kind=None, computed_at=after)
    texts: dict[str, str] = {}
    if kind in ("passed", "tree_changed"):
        texts[name] = record_text(computed_at=after)
    elif kind == "failed":
        texts[name] = record_text(status="FAILED", computed_at=after)
    elif kind == "no_status":
        texts[name] = record_text(status=None, computed_at=after)
    elif kind == "other_slug":
        texts[name] = record_text(task_slug="other", computed_at=after)
    elif kind == "stale_since":
        texts[name] = record_text(computed_at=before)
    elif kind == "no_computed_at":
        texts[name] = record_text(computed_at=None)
    elif kind == "bad_computed_at":
        texts[name] = record_text(computed_at="yesterday-ish")
    elif kind == "real_newest":
        texts[older] = record_text(computed_at=after)
        texts[name] = real
    elif kind == "real_beside":
        texts[older] = real
        texts[name] = record_text(computed_at=after)
    elif kind == "real_approved":
        texts[name] = record_text(status="APPROVED", review_kind=None, computed_at=after)
    elif kind == "sibling_only":
        texts[f"REVIEW-{SLUG}-extra-{RECORD_DATE}.md"] = record_text(computed_at=after)
    elif kind == "unparseable":
        texts[name] = "---\nstatus: [PASSED\n---\n"
    elif kind != "none":
        raise ValueError(f"unknown record kind {kind!r}")
    for file_name, text in texts.items():
        (docs / file_name).write_text(text, encoding="utf-8")


def mark_fresh(checkout: Path) -> None:
    """A passing verification marker for the checkout's current tree (verify Check 2's)."""
    from harness_maker.observability import verification_cache

    key = verification_cache.compute_relevant_skip_key(checkout)
    verification_cache.mark_passed(key, project_root=str(checkout))


def change_tree(checkout: Path) -> None:
    """Edit a tracked source file, which moves `compute_relevant_skip_key`."""
    (checkout / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")


def build(root: Path, case: Case) -> list[str]:
    """Build the fixture for `case` under `root`; return the boundary argv."""
    from harness_maker import autopilot, autopilot_ledger
    from harness_maker.models import AtomicStage

    init_repo(root)
    created = datetime.now(UTC) - timedelta(minutes=10)
    write_spec(root, case.lane)
    write_record(root, case.record, marker_created=created)
    pipeline = [AtomicStage(s) for s in {**PIPELINES, **EXTRA_PIPELINES}[case.pipeline]]
    autopilot.write(root, level=case.level, pipeline=pipeline, now=created.isoformat())  # type: ignore[arg-type]
    if case.pipeline == "narrowed_review":
        autopilot.narrow(root, until="review", session_id=None)
    autopilot_ledger.append_event(root, event="advance_authorized", fields={"to": case.current})
    mark_fresh(root)
    if case.record == "tree_changed":
        change_tree(root)
    argv = ["boundary", "--root", str(root), "--current", case.current]
    if case.slug:
        argv += ["--slug", SLUG]
    if case.gate is not None:
        argv += ["--judgment-gate", case.gate]
    return argv


def _masked(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in keys}


def observe(root: Path, argv: list[str]) -> dict[str, Any]:
    """Run the boundary once; return its JSON, the ledger rows and the marker, masked."""
    from harness_maker import autopilot, autopilot_caps, autopilot_ledger

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot_caps.main(argv)
    out = json.loads(buf.getvalue().strip().splitlines()[-1])
    ledger = autopilot_ledger.ledger_path(root)
    rows = [
        _masked(json.loads(line), MASKED_ROW_KEYS)
        for line in (ledger.read_text(encoding="utf-8").splitlines() if ledger.is_file() else [])
        if line.strip()
    ]
    path = autopilot.marker_path(root, session_id=None)
    marker = (
        _masked(json.loads(path.read_text(encoding="utf-8")), MASKED_MARKER_KEYS)
        if path.is_file()
        else None
    )
    return {"json": out, "rows": rows, "marker": marker}


#: AC-004's (lane, record) pairs; the last one is fixed to the review/verify stages.
AC004_PAIRS: tuple[tuple[str, str], ...] = (
    ("full", "none"),
    ("full", "passed"),
    ("absent", "passed"),
    ("Light", "passed"),
    ("unparseable", "passed"),
    ("none", "passed"),
    ("untrusted", "passed"),
    ("light", "none"),
    ("light", "failed"),
    ("light", "real_newest"),
)
LEVELS = ("auto_safe", "auto_full")
GATES: tuple[str | None, ...] = (None, "clear", "pending", "blocked")


def _stages(pipeline: str) -> tuple[str, ...]:
    if pipeline == "narrowed_review":
        return DEFAULT_PIPELINE[: DEFAULT_PIPELINE.index("review") + 1]
    return PIPELINES[pipeline]


def ac004_cases() -> list[Case]:
    """AC-004's input domain, in a fixed order."""
    cases: list[Case] = []
    for lane, record in AC004_PAIRS:
        for pipeline in PIPELINES:
            for current in _stages(pipeline):
                for level in LEVELS:
                    for gate in GATES:
                        cases.append(Case(lane, record, current, level, gate, pipeline))
    for pipeline in PIPELINES:
        for current in ("review", "verify"):
            if current not in _stages(pipeline):
                continue
            for level in LEVELS:
                for gate in GATES:
                    cases.append(Case("light", "passed", current, level, gate, pipeline))
    # No slug on an otherwise passing light check: the skip needs a slug.
    for level in LEVELS:
        cases.append(Case("light", "passed", "execute", level, None, "default", slug=False))
    return cases


def isolate_env(home: Path) -> dict[str, str | None]:
    """Point HOME, git config and the verification cache at `home`; return the old values."""
    keys = {
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(home / "no-global"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "HARNESS_MAKER_CACHE_DIR": str(home / "cache"),
    }
    old: dict[str, str | None] = {k: os.environ.get(k) for k in (*keys, "HM_SESSION_ID")}
    os.environ.update(keys)
    os.environ.pop("HM_SESSION_ID", None)
    return old


#: AC-012's rows: (case, lane kind, record kind, fresh cache).
DIGEST_CASES: tuple[tuple[str, str, str, bool], ...] = (
    ("approved light, PLAN, PASSED record, fresh cache", "light", "passed", True),
    ("lane full, same artifacts", "full", "passed", True),
    ("approved light, PLAN, PASSED record, cache not fresh", "light", "passed", False),
    ("unapproved light, PLAN, PASSED record, fresh cache", "untrusted", "passed", True),
    ("approved light, PLAN, no REVIEW record", "light", "none", True),
    ("approved light, newest a real CHANGES_REQUESTED review", "light", "real_newest", True),
)


def build_digest(root: Path, lane: str, record: str, fresh: bool) -> None:
    """A task checkout for `world_model_digest.next_stage(root, SLUG, root)`."""
    init_repo(root)
    write_spec(root, lane)
    docs = root / "work-docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / f"PLAN-{SLUG}.md").write_text(f"---\ntype: plan\ntask_slug: {SLUG}\n---\n")
    write_record(root, record, marker_created=datetime.now(UTC) - timedelta(minutes=10))
    mark_fresh(root)
    if not fresh:
        change_tree(root)


#: Cases whose whole e7dd6648 observation is kept in the golden, not only its hash: every
#: execute case (where the skip acts) and verify's default-pipeline auto_full boundary, which
#: is AC-003's merge_gate oracle.
FULL_OBSERVATION_STAGES = ("execute",)
VERIFY_ORACLE_KEY = "light+passed/verify/auto_full/absent/default"


def keeps_observation(case: Case) -> bool:
    return case.current in FULL_OBSERVATION_STAGES or case.key == VERIFY_ORACLE_KEY


def observation_sha(obs: dict[str, Any]) -> str:
    """The canonical hash AC-004 compares: sorted keys, no whitespace."""
    import hashlib

    canon = json.dumps(obs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()
