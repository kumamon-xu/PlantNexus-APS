"""Public command-line entry for Enterprise Extension scaffolding and checks."""

from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from aps_extension_sdk import canonical_json_bytes
from aps_extension_tooling.conformance import (
    conform_extension_set,
    conform_project,
    scaffold_project,
)
from aps_extension_tooling.packaging import write_artifact
from aps_extension_tooling.project import ConformanceError


ROOT = Path(__file__).resolve().parents[1]


def _write_report(path: Path | None, report: dict[str, object]) -> None:
    if path is not None:
        write_artifact(path, canonical_json_bytes(report) + b"\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold and verify standalone APS Enterprise Extensions"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scaffold = subparsers.add_parser("scaffold")
    scaffold.add_argument("--template", type=Path)
    scaffold.add_argument("--output", type=Path, required=True)
    scaffold.add_argument("--extension-id", required=True)
    scaffold.add_argument("--distribution-name", required=True)
    scaffold.add_argument("--package-name", required=True)
    scaffold.add_argument("--owner", required=True)
    scaffold.add_argument("--repository-url", required=True)
    scaffold.add_argument("--license-expression", required=True)
    scaffold.add_argument("--source-commit", required=True)
    scaffold.add_argument("--report", type=Path)
    scaffold.add_argument("--skip-clean-install", action="store_true")

    check = subparsers.add_parser("check")
    check.add_argument("--project", type=Path, required=True)
    check.add_argument("--output", type=Path)
    check.add_argument("--report", type=Path)
    check.add_argument("--skip-clean-install", action="store_true")

    check_set = subparsers.add_parser("check-set")
    check_set.add_argument("--project", type=Path, action="append", required=True)
    check_set.add_argument("--output", type=Path)
    check_set.add_argument("--report", type=Path)
    check_set.add_argument("--skip-clean-install", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "scaffold":
            template = (
                args.template.resolve()
                if args.template is not None
                else root / "templates/enterprise-extension"
            )
            project_root = scaffold_project(
                template_root=template,
                output_root=args.output.resolve(),
                repository_root=root,
                extension_id=args.extension_id,
                distribution_name=args.distribution_name,
                package_name=args.package_name,
                owner=args.owner,
                repository_url=args.repository_url,
                license_expression=args.license_expression,
                source_commit=args.source_commit,
            )
            result = conform_project(
                project_root,
                repository_root=root,
                output_directory=None,
                clean_install=not args.skip_clean_install,
            )
            report = {
                "report_version": "enterprise-extension-scaffold-report.v1",
                "status": "PASS",
                "project_id": result.project.project_id,
                "conformance": result.report,
                "git_repository_created": False,
                "remote_repository_created": False,
                "issues": [],
            }
        elif args.command == "check":
            result = conform_project(
                args.project.resolve(),
                repository_root=root,
                output_directory=args.output.resolve() if args.output else None,
                clean_install=not args.skip_clean_install,
            )
            report = result.report
        else:
            results = tuple(
                conform_project(
                    project.resolve(),
                    repository_root=root,
                    output_directory=args.output.resolve() if args.output else None,
                    clean_install=not args.skip_clean_install,
                )
                for project in args.project
            )
            with TemporaryDirectory(prefix="aps-extension-set-") as temporary:
                _, report = conform_extension_set(
                    results, runtime_directory=Path(temporary)
                )
        _write_report(args.report, report)
        print(canonical_json_bytes(report).decode("utf-8"))
        return 0
    except ConformanceError as error:
        report = {
            "report_version": "enterprise-extension-conformance-failure.v1",
            "status": "FAIL",
            "error": {
                "code": error.code,
                "field": error.field,
                "message": error.safe_message,
            },
            "payload_included": False,
            "path_included": False,
            "issues": [error.code],
        }
        _write_report(getattr(args, "report", None), report)
        print(canonical_json_bytes(report).decode("utf-8"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
