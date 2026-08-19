"""Per-round scratch file so a measured number never passes through the model.

Every measured field on `ReviewTelemetryRecord` is nullable, and the row is assembled by the
model from a prose instruction. Measured on this repository's own ledger, 69 rows:

    churn_ratio 0/69 · churn_measured_n 0/69 · lenses_exercised 0/69 · confirm_pass_ran 0/69

The nine **required** fields are present in all 69. That is the whole mechanism: a schema
optional is a prompt optional, and "always, per round" in prose does not survive it. The cost
was not hypothetical — `review_churn.DEFAULT_CHURN_RATIO` documents a live gate threshold set
from a second estimate rather than the recalibration it asked for, because across four
repositories all 123 rows had `churn_ratio` absent.

So the producers write here and `review_telemetry emit` reads. `emit` **strips** these keys
from the model-supplied row, which is what makes transcription impossible rather than merely
discouraged; a value the model supplied anyway is reported as drift and discarded.

Keyed by (slug, round) and NOT by run id: `emit` derives the path from the row's own required
`slug`/`round`, so this costs the templates no extra argument and cannot be passed a path that
does not match the row it lands on. The accepted limitation is that two `/hm:review`
invocations on one slug reuse a round's key — harmless in practice because each round's
producer overwrites its own key moments before `emit` reads it, and the file is scratch under
the already-gitignored observability directory.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_OBSERVABILITY_DIR = Path(".claude/observability")
ROUND_DIRNAME = ".hm-round"

#: The fields a producer owns. `emit` takes these from the record and from nowhere else.
#: Adding a measured field means adding it here — a field absent from this tuple keeps the
#: old prose-populated behaviour, which is the failure this module exists to end.
MEASURED_KEYS: tuple[str, ...] = (
    "disposition_counts",
    "churn_ratio",
    "churn_max_path",
    "churn_measured_n",
    "churn_excluded_n",
)


def _safe(component: str, *, field: str) -> str:
    """A slug reaches this out of rendered template prose, so it is attacker-reachable.

    Same rule as `stage_agent_ledger._safe_component`: every path component is model-
    substituted, so sanitising one and trusting the rest is how `slug='../../..'` escapes.
    """
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in str(component))
    cleaned = cleaned.strip("-") or "unnamed"
    if len(cleaned) > 200:
        cleaned = cleaned[:200]
    if not cleaned:
        raise ValueError(f"{field} is empty after sanitisation")
    return cleaned


def record_path(root: Path, slug: str, round_n: int) -> Path:
    store = (root.resolve() / DEFAULT_OBSERVABILITY_DIR / ROUND_DIRNAME).resolve()
    dest = store / f"{_safe(slug, field='slug')}-r{int(round_n)}.json"
    # Containment is the invariant, sanitising is only the rule: mkdir follows symlinks, so a
    # clean name is not by itself proof the write lands inside the store.
    if not dest.resolve().parent.is_relative_to(store):
        msg = f"round record {dest} escapes the store {store}"
        raise ValueError(msg)
    return dest


def merge(root: Path, slug: str, round_n: int, values: dict[str, Any]) -> Path:
    """Fold one producer's measured keys into this round's record.

    Read-modify-write rather than overwrite, because two producers write the same file:
    `finalize` contributes the dispositions and `review_churn measure` the churn, in that
    order, and an overwrite by the second would silently drop the first.

    Off-vocabulary keys are ignored rather than rejected. A producer growing a new output key
    must not start failing a round; it simply does not reach the row until `MEASURED_KEYS`
    names it, which is a visible omission rather than a crash in the middle of a review.
    """
    path = record_path(root, slug, round_n)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = read(root, slug, round_n)
    current.update({k: v for k, v in values.items() if k in MEASURED_KEYS})
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(current, handle, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def read(root: Path, slug: str, round_n: int) -> dict[str, Any]:
    """The measured keys recorded for this round, or `{}` when no producer has run.

    Unreadable and malformed both return `{}` — the caller's job is to report the resulting
    absence loudly, and raising here would fail a review over a scratch file.
    """
    try:
        raw = record_path(root, slug, round_n).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in MEASURED_KEYS}
