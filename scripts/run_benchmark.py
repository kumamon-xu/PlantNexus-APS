"""Run one P2 XS/S/M synthetic benchmark and emit machine evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.simulation.benchmarks import (
    BenchmarkContractError,
    BenchmarkExecutionError,
    run_benchmark,
)


type JsonObject = dict[str, Any]


def _code_commit() -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    if value == "uncommitted" or (
        len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return "uncommitted"


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _failure_report(profile: str, error: Exception) -> JsonObject:
    code = getattr(error, "code", type(error).__name__)
    return {
        "report_version": "benchmark-failure-report.v1",
        "status": "FAIL",
        "task_id": "TASK-P2-12",
        "profile": profile,
        "code_commit": _code_commit(),
        "error": {
            "code": str(code),
            "field": getattr(error, "field", None),
            "message": getattr(error, "message", str(error)),
        },
        "boundaries": {
            "correctness_failure": "HARD_FAIL",
            "partial_success_claim": "PROHIBITED",
            "production_sla": "NOT_ESTABLISHED_OPEN_012",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--profile", choices=("xs", "s", "m"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_benchmark(
            root=args.root.resolve(),
            profile_name=args.profile,
            require_baseline=True,
        )
    except (BenchmarkContractError, BenchmarkExecutionError, OSError) as error:
        _write_report(args.report, _failure_report(args.profile, error))
        print(f"FAIL TASK-P2-12 profile={args.profile}: {error}")
        return 1
    _write_report(args.report, report)
    print(
        f"PASS TASK-P2-12 profile={args.profile} "
        f"checks={report['check_count']} warnings={len(report['warnings'])} "
        f"problem={report['problem']['problem_hash']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
