"""Measure workflow baseline metrics for optimization delta tracking.

Collects per-call-site wall-clock and structural metrics, writes to
~/.cache/harness-maker/baseline.json (respects HARNESS_MAKER_CACHE_DIR).

Usage:
    uv run python scripts/measure_workflow_baseline.py [--compare baseline.json]
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def _cache_dir() -> Path:
    override = os.environ.get("HARNESS_MAKER_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "harness-maker"


def _time_command(cmd: list[str], cwd: Path | None = None) -> tuple[float, int]:
    """Run a command, return (wall_seconds, exit_code)."""
    start = time.monotonic()
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    elapsed = time.monotonic() - start
    return elapsed, result.returncode


def _machine_fingerprint() -> dict[str, str]:
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or platform.machine(),
        "ram_gb": _ram_gb(),
        "python": platform.python_version(),
    }


def _ram_gb() -> str:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return f"{kb / 1024 / 1024:.1f}"
    except (OSError, ValueError):
        pass
    return "unknown"


def _count_drift_gates(project_dir: Path) -> dict[str, int]:
    """Static scan of rendered stage templates for drift gate sections."""
    stages_dir = project_dir / ".claude" / "commands" / "hm"
    counts: dict[str, int] = {}

    drift_pattern = re.compile(r"(?i)drift\s*gate|drift\s*check|drift_verdict", re.IGNORECASE)

    for md_file in sorted(stages_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        matches = drift_pattern.findall(text)
        if matches:
            counts[md_file.stem] = len(matches)

    return counts


def _count_drift_in_fused_workflow(project_dir: Path) -> int:
    """Count drift gate mentions in exec-rev-wrap-ver specifically."""
    fused = project_dir / ".claude" / "commands" / "hm" / "exec-rev-wrap-ver.md"
    if not fused.is_file():
        return -1
    text = fused.read_text(encoding="utf-8")
    pattern = re.compile(r"(?i)drift\s*gate|drift\s*check|drift_verdict")
    return len(pattern.findall(text))


def _estimate_review_token_sizes(project_dir: Path) -> dict[str, int]:
    """Rough char-count estimates of review template sections as proxy for tokens."""
    review = project_dir / ".claude" / "commands" / "hm" / "review.md"
    if not review.is_file():
        return {"review_total_chars": 0, "estimated_total_tokens": 0}
    text = review.read_text(encoding="utf-8")
    return {
        "review_total_chars": len(text),
        "estimated_total_tokens": len(text) // 4,
    }


def _count_crawler_sources() -> int:
    """Count the number of crawler source modules (= expected HTTP call sites)."""
    try:
        from harness_maker.crawler import (  # noqa: F401
            anthropic_blog,
            arxiv,
            github_releases,
            osv_dev,
        )

        return 4
    except ImportError:
        return -1


def measure_baseline(project_dir: Path) -> dict[str, object]:
    """Collect all baseline axes."""
    results: dict[str, object] = {
        "measured_at": datetime.now(tz=UTC).isoformat(),
        "project_dir": str(project_dir),
        "machine": _machine_fingerprint(),
    }

    pytest_secs, pytest_rc = _time_command(
        ["uv", "run", "pytest", "-q", "--tb=short", "-x"],
        cwd=project_dir,
    )
    results["pytest_seconds"] = round(pytest_secs, 2)
    results["pytest_exit_code"] = pytest_rc

    mypy_secs, mypy_rc = _time_command(
        ["uv", "run", "mypy", "--strict", "src/"],
        cwd=project_dir,
    )
    results["mypy_seconds"] = round(mypy_secs, 2)
    results["mypy_exit_code"] = mypy_rc

    ruff_secs, ruff_rc = _time_command(
        ["ruff", "check", "."],
        cwd=project_dir,
    )
    results["ruff_seconds"] = round(ruff_secs, 2)
    results["ruff_exit_code"] = ruff_rc

    results["drift_call_count_per_file"] = _count_drift_gates(project_dir)
    results["drift_call_count_fused_exec_rev_wrap_ver"] = _count_drift_in_fused_workflow(
        project_dir
    )

    results["review_template_sizes"] = _estimate_review_token_sizes(project_dir)

    results["crawler_source_count"] = _count_crawler_sources()

    return results


def save_baseline(data: dict[str, object], output_path: Path | None = None) -> Path:
    """Atomic-write baseline JSON to cache dir."""
    if output_path is None:
        output_path = _cache_dir() / "baseline.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    import tempfile

    fd, tmp = tempfile.mkstemp(
        dir=str(output_path.parent),
        prefix=f".{output_path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, output_path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return output_path


def compare_baselines(current: dict[str, object], baseline_path: Path) -> str:
    """Generate a delta comparison table (markdown)."""
    with open(baseline_path, encoding="utf-8") as f:
        prior = json.load(f)

    lines = ["## Baseline Delta Comparison\n"]
    lines.append("| Metric | Before | After | Delta |")
    lines.append("|--------|--------|-------|-------|")

    for key in ["pytest_seconds", "mypy_seconds", "ruff_seconds"]:
        before = prior.get(key, "N/A")
        after = current.get(key, "N/A")
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            delta = after - before
            pct = (delta / before * 100) if before else 0
            lines.append(f"| {key} | {before:.2f}s | {after:.2f}s | {delta:+.2f}s ({pct:+.1f}%) |")
        else:
            lines.append(f"| {key} | {before} | {after} | — |")

    fused_before = prior.get("drift_call_count_fused_exec_rev_wrap_ver", "N/A")
    fused_after = current.get("drift_call_count_fused_exec_rev_wrap_ver", "N/A")
    lines.append(f"| drift (fused) | {fused_before} | {fused_after} | — |")

    return "\n".join(lines)


REQUIRED_AXES = [
    "measured_at",
    "project_dir",
    "machine",
    "pytest_seconds",
    "mypy_seconds",
    "ruff_seconds",
    "drift_call_count_per_file",
    "drift_call_count_fused_exec_rev_wrap_ver",
    "review_template_sizes",
    "crawler_source_count",
]


def main() -> None:
    project_dir = Path.cwd()
    compare_path: Path | None = None

    args = sys.argv[1:]
    if "--compare" in args:
        idx = args.index("--compare")
        if idx + 1 < len(args):
            compare_path = Path(args[idx + 1])
            if not compare_path.is_file():
                print(f"ERROR: comparison baseline not found: {compare_path}", file=sys.stderr)
                sys.exit(1)

    print(f"Measuring baseline for {project_dir} ...", file=sys.stderr)
    data = measure_baseline(project_dir)

    for axis in REQUIRED_AXES:
        assert axis in data, f"missing required axis: {axis}"

    out = save_baseline(data)
    print(f"Baseline saved to {out}", file=sys.stderr)
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if compare_path:
        report = compare_baselines(data, compare_path)
        print("\n" + report, file=sys.stderr)


if __name__ == "__main__":
    main()
