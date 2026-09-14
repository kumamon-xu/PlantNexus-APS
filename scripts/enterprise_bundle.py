"""Assemble or verify the unsigned TEST/SIMULATION offline candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra.enterprise.bundle.builder import assemble  # noqa: E402
from infra.enterprise.bundle.verify import extract, verify  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    for name in ("image-report", "runtime-archive", "runtime-sbom", "output"):
        build.add_argument("--" + name, type=Path, required=True)
    build.add_argument("--candidate", action="store_true")
    check = commands.add_parser("verify")
    check.add_argument("--archive", type=Path, required=True)
    check.add_argument("--expected-sha256", required=True)
    check.add_argument("--extract-to", type=Path)
    for sub in (build, check):
        sub.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = assemble(args)
        elif args.extract_to:
            result = extract(args.archive, args.expected_sha256, args.extract_to)
        else:
            result = verify(args.archive, args.expected_sha256)
    except Exception as error:
        result = dict(
            schema_version="enterprise-bundle-report.v1",
            task_id="TASK-P8-27",
            status="FAIL",
            issues=[
                str(error)
                if isinstance(error, ValueError) and str(error).isupper()
                else type(error).__name__
            ],
            production_ready=False,
        )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "issues")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
