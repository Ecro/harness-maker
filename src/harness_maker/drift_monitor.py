"""Trajectory drift monitor — hybrid cosine pre-filter + LLM precision scoring.

Detects when execution trajectory diverges from the original intent (SPEC/PLAN/prompt).
ADR-003: multi-layer baseline fallback (SPEC → PLAN → prompt).
ADR-010: hybrid scoring (cosine pre-filter → LLM when cos_sim < threshold).
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    """Embedding provider interface for drift scoring."""

    def embed(self, text: str) -> list[float]: ...


class LLMJudge(Protocol):
    """LLM judge interface for precise drift scoring."""

    def judge_drift(self, baseline: str, current: str) -> float: ...


class SimpleHashEmbedding:
    """Deterministic hash-based pseudo-embedding for testing and fallback.

    Not semantically meaningful — only useful for testing the drift pipeline
    mechanics. Production use should provide a real embedding model.
    """

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    def embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).hexdigest()
        values: list[float] = []
        for i in range(self._dim):
            byte_idx = i % len(h)
            values.append(int(h[byte_idx], 16) / 15.0)
        return values


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def resolve_baseline(
    spec_path: Path | None = None,
    plan_path: Path | None = None,
    prompt: str = "",
) -> tuple[str, str]:
    """Multi-layer fallback: SPEC → PLAN → prompt (ADR-003)."""
    if spec_path and spec_path.is_file():
        text = spec_path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            return text, "spec"
    if plan_path and plan_path.is_file():
        text = plan_path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            return text, "plan"
    if prompt.strip():
        return prompt.strip(), "prompt"
    return "", "none"


class DriftMonitor:
    """Hybrid drift detector per ADR-010."""

    def __init__(
        self,
        *,
        embedding: EmbeddingProvider | None = None,
        judge: LLMJudge | None = None,
        threshold: float = 0.7,
    ) -> None:
        self._embedding = embedding or SimpleHashEmbedding()
        self._judge = judge
        self._threshold = threshold

    def score(
        self,
        baseline_text: str,
        current_text: str,
    ) -> dict[str, Any]:
        """Compute drift score.

        Returns dict with cos_sim, drift_score, used_llm, and threshold.
        drift_score is 0.0 (no drift) to 1.0 (complete drift).
        """
        if not baseline_text.strip() or not current_text.strip():
            return {
                "cos_sim": 0.0,
                "drift_score": 1.0,
                "used_llm": False,
                "threshold": self._threshold,
                "warning": "empty baseline or current text",
            }

        baseline_emb = self._embedding.embed(baseline_text)
        current_emb = self._embedding.embed(current_text)
        cos_sim = cosine_similarity(baseline_emb, current_emb)

        result: dict[str, Any] = {
            "cos_sim": round(cos_sim, 4),
            "threshold": self._threshold,
            "used_llm": False,
        }

        if cos_sim >= self._threshold:
            result["drift_score"] = round(1.0 - cos_sim, 4)
            return result

        if self._judge is not None:
            drift = self._judge.judge_drift(baseline_text, current_text)
            result["drift_score"] = round(drift, 4)
            result["used_llm"] = True
        else:
            result["drift_score"] = round(1.0 - cos_sim, 4)

        return result

    def check(
        self,
        *,
        spec_path: Path | None = None,
        plan_path: Path | None = None,
        prompt: str = "",
        current_output: str,
        warn_threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Full drift check with baseline resolution and warning."""
        baseline_text, source = resolve_baseline(spec_path, plan_path, prompt)
        if not baseline_text:
            return {
                "baseline_source": "none",
                "drift_score": 0.0,
                "warning": "no baseline available — drift check skipped",
            }
        result = self.score(baseline_text, current_output)
        result["baseline_source"] = source
        if result["drift_score"] > warn_threshold:
            result["warning"] = (
                f"drift score {result['drift_score']:.2f} exceeds "
                f"warn threshold {warn_threshold:.2f}"
            )
        return result


def main() -> int:
    """CLI entry point for `python -m harness_maker.drift_monitor`.

    Reads JSON from stdin with keys baseline_spec_path / baseline_plan_path /
    baseline_prompt / current_text / threshold (optional), runs the hybrid
    drift check, and prints a single-line JSON result to stdout. Stage
    prompts in trajectory-monitor.md.j2 invoke this module rather than
    re-implementing the logic in prose.
    """
    import json
    import sys

    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        sys.stderr.write("drift_monitor: stdin is not valid JSON\n")
        return 1
    if not isinstance(data, dict):
        sys.stderr.write("drift_monitor: stdin must be a JSON object\n")
        return 1
    spec_path_str = data.get("baseline_spec_path")
    plan_path_str = data.get("baseline_plan_path")
    prompt_text = data.get("baseline_prompt", "") or ""
    current_text = data.get("current_text", "") or ""
    threshold_raw = data.get("threshold", 0.7)
    try:
        threshold = float(threshold_raw)
    except (TypeError, ValueError):
        threshold = 0.7
    monitor = DriftMonitor(threshold=threshold)
    result = monitor.check(
        spec_path=Path(spec_path_str) if isinstance(spec_path_str, str) and spec_path_str else None,
        plan_path=Path(plan_path_str) if isinstance(plan_path_str, str) and plan_path_str else None,
        prompt=prompt_text if isinstance(prompt_text, str) else "",
        current_output=current_text if isinstance(current_text, str) else "",
    )
    score = result.get("drift_score", 0.0)
    if isinstance(score, int | float) and score > threshold:
        result["verdict"] = "drift"
    else:
        result["verdict"] = "on-track"
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(main())
