"""Uncached presence detection for the external CLIs onboarding can offer."""

from __future__ import annotations

import shutil

# Key = the name used in `harness.yaml` / `SECOND_OPINION_MODELS`; value = the binary.
# They differ for antigravity (`agy`), which is exactly the mapping a reader gets wrong.
_BINARIES: dict[str, str] = {
    "codex": "codex",
    "antigravity": "agy",
    "cursor": "cursor",
}

# `installed` means the binary resolves on PATH. It does NOT mean `codex login` has been
# run or that `agy` is authenticated — nothing here probes auth, and every user-facing
# string built from this must say so, or "detected" reads as "ready" and the user enables a
# model whose first real call degrades to a skip.
INSTALLED_MEANS = "binary present on PATH; authentication not verified"


def detect_tools() -> dict[str, dict[str, bool]]:
    """Probe PATH on every call — never cached (ADR-001 of PLAN-onboarding-interview-ux).

    WHY not a `ProjectProfile` field: that is served from `detection_cache`, whose only
    invalidation signals are a 24h ceiling and project-manifest mtime. Installing a CLI
    touches no project manifest, so a cached answer would report a tool installed minutes
    ago as absent — and a permanently-wrong cache is indistinguishable from a correct one.
    """
    return {
        key: {"installed": shutil.which(binary) is not None} for key, binary in _BINARIES.items()
    }
