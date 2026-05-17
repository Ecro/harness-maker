"""3-section health dashboard writer (0.13.0).

PLAN health-consolidation Phase 1 / ADR-002 (amended by ADR-006): the
single ``Health`` score is split into three orthogonal fields written as
distinct sections of ``dashboard.md``:

  - ``Structural``      — ai_readiness layer 1+3 score (verify Check 3)
  - ``External risks``  — crawler + relevance + stale-asset count
                          (verify Check 4)
  - ``Personalization`` — composite + tier + ADR-011 ActionItems
                          (NOT read by verify)

The writer is intentionally pure formatting; the three section payloads
are computed by their owning modules (``ai_readiness``, the future
external-risks orchestrator inside ``cli.health``, and
``personalization_audit.run_audit`` respectively). Atomic write per
CLAUDE.md WSL2/NTFS rule.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker.io_utils import atomic_write

_DASHBOARD_RELPATH = Path(".claude") / "observability" / "dashboard.md"
_VALID_TIERS = {"bronze", "silver", "gold", "platinum"}


def _coerce_score(value: object, *, default: int = 0) -> int:
    """Map an int-like payload to a clamped 0-100 int.

    Why defensive: the three section dicts are assembled by independent
    layers; a mis-shaped payload should write a visible "0 / 100" rather
    than crash the whole /hm:health command.
    """
    if isinstance(value, bool):
        # bool is an int subclass — exclude explicitly so True/False can't
        # accidentally satisfy the numeric branch with 1/0.
        return default
    if isinstance(value, int):
        return max(0, min(100, value))
    if isinstance(value, float):
        return max(0, min(100, round(value)))
    return default


def _format_list_block(items: list[Any]) -> str:
    """Render a list as either ``[]`` (empty) or a JSON array on one line.

    Why JSON not YAML: dashboard.md is consumed by the verify-stage
    template and by humans skim-reading. JSON keeps the schema mechanically
    parseable without dragging yaml into reader scripts.
    """
    if not items:
        return "[]"
    return json.dumps(items, ensure_ascii=False, sort_keys=False)


def _format_dict_block(d: dict[str, Any]) -> str:
    """Single-line JSON object for compact layer-score display."""
    if not d:
        return "{}"
    return json.dumps(d, ensure_ascii=False, sort_keys=False)


def render_dashboard_markdown(
    structural: dict[str, Any],
    external_risks: dict[str, Any],
    personalization: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> str:
    """Render the 3-section dashboard.md body.

    ``generated_at`` defaults to ``datetime.now(UTC).isoformat()``; tests
    inject a frozen value for snapshot determinism. The frontmatter
    follows the harness-maker convention (``generated_by`` first, then the
    timestamp) so future fingerprint tooling can dispatch on it.
    """
    if generated_at is None:
        generated_at = datetime.now(UTC).isoformat()

    structural_score = _coerce_score(structural.get("score"))
    signals_failed = structural.get("signals_failed", [])
    if not isinstance(signals_failed, list):
        signals_failed = []

    pending = external_risks.get("pending", 0)
    if not isinstance(pending, int) or isinstance(pending, bool):
        pending = 0
    items = external_risks.get("items", [])
    if not isinstance(items, list):
        items = []

    composite = _coerce_score(personalization.get("composite"))
    tier = personalization.get("tier", "bronze")
    if not isinstance(tier, str) or tier not in _VALID_TIERS:
        tier = "bronze"
    layers = personalization.get("layers", {})
    if not isinstance(layers, dict):
        layers = {}
    action_items = personalization.get("action_items", [])
    if not isinstance(action_items, list):
        action_items = []

    lines = [
        "---",
        "generated_by: harness-maker",
        f"generated_at: {generated_at}",
        "---",
        "# Health",
        "",
        "## Structural",
        f"score: {structural_score} / 100",
        f"signals_failed: {_format_list_block(signals_failed)}",
        "",
        "## External risks",
        f"pending: {pending}",
        f"items: {_format_list_block(items)}",
        "",
        "## Personalization",
        f"composite: {composite} / 100",
        f"tier: {tier}",
        f"layers: {_format_dict_block(layers)}",
        f"action_items: {_format_list_block(action_items)}",
        "",
    ]
    return "\n".join(lines)


def write_dashboard(
    project_root: Path,
    structural: dict[str, Any],
    external_risks: dict[str, Any],
    personalization: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> Path:
    """Atomically write ``<project_root>/.claude/observability/dashboard.md``.

    Returns the written path. Calling more than once on the same project
    overwrites the previous dashboard — the schema is "latest snapshot",
    not append-only.
    """
    body = render_dashboard_markdown(
        structural,
        external_risks,
        personalization,
        generated_at=generated_at,
    )
    out = project_root / _DASHBOARD_RELPATH
    atomic_write(out, body)
    return out


# ─── Reader (verify stage + tests) ──────────────────────────────────────────


def parse_dashboard(path: Path) -> dict[str, Any] | None:
    """Return a structured view of dashboard.md, or None when the file is
    absent / unparseable / pre-0.13.0 schema.

    The 0.12.x dashboard used a single ``**Composite:** NN / 100`` scalar
    in markdown body. That schema is intentionally unparseable here so the
    verify stage cannot mistake it for a fresh baseline (ADR-004: no
    compatibility shim; missing baseline = "no-baseline PASS").
    """
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Must have our frontmatter to be considered 0.13.0+ schema. The old
    # single-scalar dashboard had no harness-maker frontmatter at all (it
    # was rendered from a jinja template without our `generated_by` block).
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    header = text[4:end]
    if "generated_by: harness-maker" not in header:
        return None
    body = text[end + len("\n---\n") :]

    out: dict[str, Any] = {
        "structural": {"score": None, "signals_failed": []},
        "external_risks": {"pending": None, "items": []},
        "personalization": {
            "composite": None,
            "tier": None,
            "layers": {},
            "action_items": [],
        },
    }
    section: str | None = None
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            label = stripped.removeprefix("## ").strip().lower()
            if label == "structural":
                section = "structural"
            elif label == "external risks":
                section = "external_risks"
            elif label == "personalization":
                section = "personalization"
            else:
                section = None
            continue
        if section is None or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if section == "structural":
            if key == "score":
                out["structural"]["score"] = _parse_score(value)
            elif key == "signals_failed":
                out["structural"]["signals_failed"] = _parse_json_list(value)
        elif section == "external_risks":
            if key == "pending":
                out["external_risks"]["pending"] = _parse_int(value)
            elif key == "items":
                out["external_risks"]["items"] = _parse_json_list(value)
        elif section == "personalization":
            if key == "composite":
                out["personalization"]["composite"] = _parse_score(value)
            elif key == "tier":
                out["personalization"]["tier"] = value
            elif key == "layers":
                out["personalization"]["layers"] = _parse_json_object(value)
            elif key == "action_items":
                out["personalization"]["action_items"] = _parse_json_list(value)
    # If structural.score never set, the body is malformed — treat as old-schema.
    if out["structural"]["score"] is None:
        return None
    return out


def _parse_score(value: str) -> int | None:
    head = value.split("/", 1)[0].strip()
    try:
        return int(head)
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        return None


def _parse_json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
