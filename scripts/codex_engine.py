"""Run under the pinned Python engine; emit only an observed JSON receipt."""

import argparse
import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import yaml

from harness_maker.io_utils import load_harness_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--preset", choices=["Side", "Production"])
    parser.add_argument("--locale")
    args = parser.parse_args()
    engine = None
    try:
        engine = version("harness-maker")
        if engine != args.expected:
            raise ValueError("engine_mismatch")
        project = args.project.resolve()
        config = project / ".claude/harness.yaml"
        current = load_harness_yaml(config) if config.exists() else {}
        targets = list(current.get("targets", []))
        if "codex" not in targets:
            targets.append("codex")
        cmd = [
            sys.executable,
            "-I",
            "-m",
            "harness_maker.cli",
            "make",
            str(project),
            "--autoloop",
            "--targets",
            ",".join(targets),
        ]
        if args.update:
            cmd.append("--update")
        for key in ("preset", "locale"):
            value = getattr(args, key)
            if value is not None:
                cmd.extend(["--" + key.replace("_", "-"), value])
        project.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            cmd, cwd=project, capture_output=True, text=True, shell=False, timeout=240, check=True
        )
        docs = list(yaml.safe_load_all(config.read_text()))
        generated = next(
            (
                d.get("harness_maker_version")
                for d in docs
                if isinstance(d, dict) and d.get("generated_by") == "harness-maker"
            ),
            None,
        )
        assets = (
            (project / "AGENTS.md").is_file()
            and (project / ".codex/config.toml").is_file()
            and (project / ".agents/skills/hm-execute/SKILL.md").is_file()
            and any((project / ".codex/agents").glob("*.toml"))
        )
        print(json.dumps({"engine": engine, "project": generated, "codex_assets": assets}))
        return 0 if generated == args.expected and assets else 1
    except (OSError, ValueError, TypeError, yaml.YAMLError, subprocess.SubprocessError):
        print(
            json.dumps(
                {
                    "engine": engine,
                    "project": None,
                    "codex_assets": False,
                    "error": "engine_generation_failed",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
