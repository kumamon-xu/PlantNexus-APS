"""CLI entry point for one bounded CNC demo benchmark run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from plantnexus_demo.benchmark import run_benchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "showcase", "upper"), default="showcase")
    parser.add_argument("--solve-seconds", type=float)
    parser.add_argument("--pipeline-only", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_benchmark(
        arguments.profile,
        solve_seconds=arguments.solve_seconds,
        run_solver=not arguments.pipeline_only,
    )
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "profile": arguments.profile,
                "report": str(arguments.report.resolve()),
                "problem_hash": report["standard_ingress"]["problem_hash"],
                "solver_status": report["solver"]["solver_status"],
                "validator_status": (
                    None
                    if report["solver"]["validator"] is None
                    else report["solver"]["validator"]["status"]
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
