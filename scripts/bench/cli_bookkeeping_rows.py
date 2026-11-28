"""Reduce bench_light_lane results + transcripts to SPEC-cli-bookkeeping AC-007 rows.

Usage: python scripts/bench/cli_bookkeeping_rows.py OUT ROWS.jsonl \
    <results.jsonl>:<claude config dir>:<arm map> ...
where <arm map> is e.g. `plain=plain,hm=hm-new` or `hm=hm-main`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# One main-session Bash call that runs the hm CLI: the `uv run --with <src> hm` prefix, or the
# `$P`/`$H` shell variable the stages bind it to.
HM_CALL = re.compile(r"--with \S+ hm\b|\$\{?[PH]\}?(?:\s|$)")


def hm_bash_calls(transcript: Path) -> int:
    n = 0
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "assistant":
            continue
        for part in obj.get("message", {}).get("content", []) or []:
            if (
                isinstance(part, dict)
                and part.get("type") == "tool_use"
                and part.get("name") == "Bash"
                and HM_CALL.search(str(part.get("input", {}).get("command", "")))
            ):
                n += 1
    return n


def main_transcripts(config: Path, run_dir: str) -> list[Path]:
    project = config / "projects" / (run_dir.rstrip("/") + "/work").replace("/", "-")
    return sorted(project.glob("*.jsonl"))


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    rows: list[str] = []
    for spec in argv[1:]:
        results, config, arms = spec.split(":")
        arm_map = dict(pair.split("=") for pair in arms.split(","))
        for line in Path(results).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["arm"] not in arm_map:
                continue
            calls = sum(hm_bash_calls(t) for t in main_transcripts(Path(config), r["run_dir"]))
            rows.append(json.dumps({
                "arm": arm_map[r["arm"]], "task": r["task"], "rep": r["rep"],
                "status": r["status"], "cost_usd": r["cost_usd"], "wall_s": r["wall_s"],
                "passed": r["passed"], "hm_bash_calls": calls, "model": r["model"],
                "harness_sha": r["harness_sha"],
            }))  # fmt: skip
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
