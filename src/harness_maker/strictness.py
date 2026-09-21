"""The one reader and the one writer of `spec.strictness` (SPEC-dev-mode-removal)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, MutableMapping
from typing import Any, Literal

logger = logging.getLogger(__name__)

Strictness = Literal["block", "warn"]
STRICTNESS_VALUES: tuple[Strictness, ...] = ("block", "warn")

#: What a preset means when the key is absent (ADR-004). Keyed by the `Preset` value string so
#: raw harness.yaml mappings and the typed model resolve through the same table.
PRESET_DEFAULT: dict[str, Strictness] = {"Production": "block", "Side": "warn"}

#: The model's own default preset, used when a mapping carries none — the same answer
#: `HarnessConfig` would give for the same file.
_ABSENT_PRESET = "Side"

#: Readers that deliberately do NOT derive from the preset. `spec_need`'s verify oracle relaxes
#: only on an explicit, valid `warn` and enforces on absence (ADR-004). It is named here, in
#: data, so the structural test can hold the set at exactly one member — a comment saying "do
#: not align this" could not be checked.
STRICTNESS_EXEMPT: frozenset[str] = frozenset({"harness_maker.spec_need._read_strictness"})


def _parts(config: Any) -> tuple[Any, Any]:
    if isinstance(config, Mapping):
        return config.get("preset"), config.get("spec")
    return getattr(config, "preset", None), getattr(config, "spec", None)


def resolve_strictness(config: Any) -> Strictness:
    """Resolve a harness config (raw mapping or `HarnessConfig`) to block/warn.

    WHY fail closed on a malformed value rather than fall through to the preset: a value was
    written because someone meant to override the default, so the default is the one answer
    known not to be what they meant.
    """
    preset, spec = _parts(config)
    if isinstance(spec, Mapping) and "strictness" in spec:
        value = spec.get("strictness")
        if value in STRICTNESS_VALUES:
            return value  # type: ignore[no-any-return]
        logger.warning("spec.strictness %r is not one of block|warn — treating it as block", value)
        return "block"
    name = getattr(preset, "value", preset)
    if name is None:
        name = _ABSENT_PRESET
    if name in PRESET_DEFAULT:
        return PRESET_DEFAULT[name]
    logger.warning("preset %r is not recognised — treating strictness as block", name)
    return "block"


def explicit_strictness(config: Any) -> Strictness | None:
    """The resolved value when the config SETS the key, else None (preset-derived).

    Exists so re-render can keep an explicit choice explicit — a value equal to the preset
    default is indistinguishable from a defaulted one once resolved, and treating it as
    defaulted would let a later `--preset` switch silently change it.
    """
    _, spec = _parts(config)
    if isinstance(spec, Mapping) and "strictness" in spec:
        return resolve_strictness(config)
    return None


def write_strictness(data: MutableMapping[str, Any], value: Strictness) -> None:
    """Set `spec.strictness` on a harness mapping, keeping every other `spec` key."""
    if value not in STRICTNESS_VALUES:
        raise ValueError(f"strictness must be one of {STRICTNESS_VALUES}, got {value!r}")
    existing = data.get("spec")
    spec = dict(existing) if isinstance(existing, Mapping) else {}
    spec["strictness"] = value
    data["spec"] = spec
