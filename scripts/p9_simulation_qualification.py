"""Reproducible P9 development calibration, sealed holdout and coverage runner."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import site
from statistics import median
import subprocess
import sys
import xml.etree.ElementTree as ET
from typing import Any, cast


def write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def environment(root: Path) -> dict[str, Any]:
    processor = platform.processor()
    if sys.platform == "linux":
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8")
        processor = next(
            (
                line.split(":", 1)[1].strip()
                for line in cpuinfo.splitlines()
                if line.startswith("model name")
            ),
            processor,
        )
    if sys.platform == "win32":
        hardware = json.loads(
            subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory | ConvertTo-Json",
                ],
                text=True,
            )
        )
        ram = int(hardware["TotalPhysicalMemory"])
    else:
        ram = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    return {
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": processor,
        "logical_cores": os.cpu_count(),
        "memory_bytes": ram,
        "python": platform.python_version(),
        "packages": {
            name: version(name)
            for name in ("ortools", "celery", "redis", "sqlalchemy", "plantnexus-aps")
        },
        "uv_lock_sha256": sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "parallelism": 1,
        "database": "SQLite isolated file",
        "worker": "Celery solo, thread-hosted real Redis consumer",
        "extension_set": "NONE for generated benchmark; configured extensions covered by B09",
        "kit": "not packaged by P9-09; exact candidate combination owned by P9-10",
    }


def isolated_measure(
    root: Path, out: Path, input_path: Path, broker: str, code: str
) -> list[dict[str, Any]]:
    """A new interpreter owns each Celery task registry and Runtime lifetime."""
    bootstrap = out.with_suffix(".py")
    output = out.with_suffix(".json")
    bootstrap.write_text(
        "import sys,json,pathlib\n"
        + f"sys.path.extend({sys.path!r})\n"
        + "import app\n"
        + "from backend.tests.integration.p9_simulation_support import measure\n"
        + f'rows=measure(pathlib.Path({str(root)!r}),pathlib.Path({str(out)!r}),json.loads(pathlib.Path({str(input_path)!r}).read_text(encoding="utf-8")),{broker!r},{code!r})\n'
        + f'pathlib.Path({str(output)!r}).write_text(json.dumps(rows,indent=2),encoding="utf-8")\n',
        encoding="utf-8",
    )
    with out.with_suffix(".log").open("x", encoding="utf-8") as stream:
        subprocess.run(
            [sys.executable, "-I", "-X", "utf8", str(bootstrap)],
            cwd=root,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=240,
        )
    return json.loads(output.read_text(encoding="utf-8"))


def run(
    root: Path,
    out: Path,
    broker: str,
    code: str,
    coverage: bool,
    development_only: bool = False,
    frozen_budget: Path | None = None,
    catalog_version: str = "v2",
) -> dict[str, Any]:
    import app
    import aps_extension_sdk
    from redis import Redis
    from app.simulation.benchmarks.p9_catalog import (
        read_catalog,
        generate_input,
        freeze_budget,
        evaluate_budget,
        catalog_path,
    )

    out.mkdir(parents=True, exist_ok=False)
    catalog = read_catalog(root, catalog_version)
    env = environment(root)
    env["redis_server_version"] = cast(Any, Redis.from_url(broker).info("server"))[
        "redis_version"
    ]
    env["redis_image"] = (
        "redis@sha256:520775a41a63e77e06c73e35d2fd9cc15921a609516818796b4ecbb813078bc7"
    )
    write_new(out / "environment.json", env)
    write_new(
        out / "import-identity.json",
        {
            "app": str(Path(app.__file__).resolve()),
            "sdk": str(Path(aps_extension_sdk.__file__).resolve()),
            "python_prefix": sys.prefix,
        },
    )
    catalog_hash = sha256(
        (root / catalog_path(catalog_version)).read_bytes()
    ).hexdigest()
    reports = {}
    baseline = json.loads(frozen_budget.read_bytes()) if frozen_budget else None
    recovery = (
        {
            "source": str(frozen_budget),
            "sha256": sha256(frozen_budget.read_bytes()).hexdigest(),
            "purpose": "HARNESS_RECOVERY_WITH_UNCHANGED_PRE_HOLDOUT_BUDGET",
        }
        if frozen_budget
        else None
    )
    holdout_authorization = None
    for split in ("development",) if development_only else ("development", "holdout"):
        if split == "holdout":
            assert baseline is not None
            holdout_authorization = {
                "purpose": (
                    "EXPOSED_V1_FAILURE_REGRESSION"
                    if catalog_version == "v1"
                    else "FIRST_QUALIFICATION_AFTER_FROZEN_BUDGET"
                ),
                "catalog_sha256": catalog_hash,
                "baseline_sha256": sha256(
                    (out / "frozen-baseline.json").read_bytes()
                ).hexdigest(),
                "implementation_sha": code,
                "recovery": recovery,
            }
            write_new(out / "holdout-access.json", holdout_authorization)
        report: dict[str, Any] = {
            "report_version": "p9-runtime-observation.v1",
            "split": split,
            "environment": env,
            "catalog_sha256": catalog_hash,
            "implementation_sha": code,
            "samples": {},
            "warmups": {},
            "issues": [],
            "result": "RUNNING",
        }
        for size in ("xs", "s", "m"):
            generated = generate_input(
                root,
                split,
                size,
                holdout_authorization=holdout_authorization,
                version=catalog_version,
            )
            replay = generate_input(
                root,
                split,
                size,
                holdout_authorization=holdout_authorization,
                version=catalog_version,
            )
            assert generated == replay, "P9_INPUT_NONDETERMINISM"
            write_new(out / f"{split}-{size}-input.json", generated)
            try:
                rows = isolated_measure(
                    root,
                    out / f"{split}-{size}",
                    out / f"{split}-{size}-input.json",
                    broker,
                    code,
                )
            except Exception as error:
                report["issues"].append(f"{size}: {type(error).__name__}: {error}")
                report["result"] = "FAIL"
                write_new(out / f"{split}-failed.json", report)
                raise
            report["warmups"][size] = rows[0]
            report["samples"][size] = rows[1:]
            hashes = {(r["input_fingerprint"], r["problem_hash"]) for r in rows}
            if len(hashes) != 1:
                report["issues"].append(f"{size}: INPUT_OR_PROBLEM_NONDETERMINISM")
            for row in rows:
                if (
                    row["status"] not in ("FEASIBLE", "OPTIMAL")
                    or row["validation_report"]["status"] != "PASS"
                ):
                    report["issues"].append(f"{size}: INVALID_CANDIDATE")
                references = row["references"]
                if any(r["status"] != "FEASIBLE" for r in references):
                    report["issues"].append(f"{size}: REFERENCE_FAILURE")
                values = [
                    r["metrics"]["weighted_tardiness_seconds"]
                    for r in references
                    if r["status"] == "FEASIBLE"
                ]
                if values and row["quality"][0]["objective_value"] > min(values):
                    report["issues"].append(f"{size}: BENCHMARK_WARNING")
        all_rows = [r for rows in report["samples"].values() for r in rows]
        report["status_counts"] = dict(Counter(r["status"] for r in all_rows))
        report["denominator"] = len(all_rows)
        report["summary"] = {
            size: {
                metric: {
                    "min": min(values),
                    "median": median(values),
                    "max": max(values),
                }
                for metric in rows[0]["measurements"]
                for values in [[r["measurements"][metric] for r in rows]]
            }
            for size, rows in report["samples"].items()
        }
        if baseline is not None:
            report["issues"].extend(evaluate_budget(report, baseline))
        if split == "development":
            historical_path = (
                root / f"benchmarks/baselines/p9-runtime.{catalog_version}.json"
            )
            report["historical_environment_comparison"] = "INITIAL_CALIBRATION"
            if historical_path.exists():
                historical = json.loads(historical_path.read_bytes())
                if historical["environment"] == env:
                    report["issues"].extend(evaluate_budget(report, historical))
                    report["historical_environment_comparison"] = (
                        "SAME_ENVIRONMENT_REGRESSION_CHECKED"
                    )
                else:
                    report["historical_environment_comparison"] = (
                        "NOT_COMPARABLE_NEW_ENVIRONMENT_CALIBRATION"
                    )
        report["result"] = "FAIL" if report["issues"] else "PASS"
        write_new(out / f"{split}-report.json", report)
        reports[split] = report
        if report["issues"] and split == "development":
            raise RuntimeError(f"P9_{split.upper()}_FAILED: {report['issues']}")
        if split == "development":
            if baseline is None:
                baseline = freeze_budget(report, catalog)
            write_new(out / "frozen-baseline.json", baseline)
    return complete_qualification(
        root,
        out,
        broker,
        code,
        catalog,
        env,
        reports,
        baseline,
        coverage,
        development_only,
        recovery,
    )


def complete_qualification(
    root: Path,
    out: Path,
    broker: str,
    code: str,
    catalog: dict[str, Any],
    env: dict[str, Any],
    reports: dict[str, Any],
    baseline: dict[str, Any] | None,
    coverage: bool,
    development_only: bool,
    recovery: dict[str, Any] | None,
    *,
    observation_source: str | None = None,
) -> dict[str, Any]:
    """Finish independent checks even when retained holdout quality is blocked."""
    from app.simulation.benchmarks.p9_catalog import catalog_path, generate_input

    catalog_version = catalog["catalog_version"].rsplit(".", 1)[1]

    catalog_hash = sha256(
        (root / catalog_path(catalog_version)).read_bytes()
    ).hexdigest()
    if any(
        report["environment"] != env or report["catalog_sha256"] != catalog_hash
        for report in reports.values()
    ):
        raise ValueError("P9_COMPLETION_OBSERVATION_IDENTITY_MISMATCH")
    issues = [issue for report in reports.values() for issue in report["issues"]]
    coverage_rows = []
    negative_rows = []
    if not development_only:
        from app.data_validation.canonical_ingress import canonical_fingerprint
        from app.snapshots import import_package_id_for

        negative = json.loads(
            (
                root / "fixtures/infeasible/P9-QUALIFICATION/negative-catalog.v1.json"
            ).read_bytes()
        )
        for case in negative["cases"]:
            generated = generate_input(
                root, "development", case["profile"], version=catalog_version
            )
            generated["scenario_id"] = "P9-NEGATIVE-" + case["id"]
            generated["expected_terminal"] = case["expected"]
            if case["id"] == "unknown-budget":
                generated["profile"]["max_wall_time_seconds"] = case[
                    "max_wall_time_seconds"
                ]
            else:
                for calendar in generated["package"]["records"]["calendars"]:
                    calendar["unavailable_intervals"] = [
                        {
                            "interval_id": calendar["calendar_id"] + "-blocked",
                            "start_at_utc": generated["build_plan"][
                                "horizon_start_utc"
                            ],
                            "end_at_utc": generated["build_plan"]["horizon_end_utc"],
                            "reason": "P9_DECLARED_INFEASIBLE",
                        }
                    ]
                generated["package"]["package_id"] = import_package_id_for(
                    generated["package"]
                )
                generated["input_fingerprint"] = canonical_fingerprint(
                    generated["package"]
                )
            input_path = out / f"negative-{case['id']}-input.json"
            write_new(input_path, generated)
            negative_rows.extend(
                isolated_measure(
                    root, out / f"negative-{case['id']}", input_path, broker, code
                )
            )
    if coverage:
        paths = sorted({p for paths in catalog["coverage"].values() for p in paths})
        pytest_args = [
            "-q",
            *paths,
            "-k",
            "not browser",
            f"--junitxml={out / 'coverage.xml'}",
        ]
        bootstrap = (
            f"import sys; sys.path.extend({sys.path!r}); "
            "import app,aps_extension_sdk,pytest; "
            f"raise SystemExit(pytest.main({pytest_args!r}))"
        )
        command = [sys.executable, "-I", "-c", bootstrap]
        with (out / "coverage.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(
                command, cwd=root, stdout=stream, stderr=subprocess.STDOUT
            )
        cases = list(ET.parse(out / "coverage.xml").getroot().iter("testcase"))
        for cell, paths in catalog["coverage"].items():
            prefixes = [p.removesuffix(".py").replace("/", ".") for p in paths]
            selected = [c for c in cases if c.get("classname", "") in prefixes]
            failures = [
                c
                for c in selected
                if any(c.find(k) is not None for k in ("failure", "error", "skipped"))
            ]
            coverage_rows.append(
                {
                    "cell": cell,
                    "tests": len(selected),
                    "result": "PASS" if selected and not failures else "FAIL",
                    "sources": paths,
                    "test_names": [c.get("name") for c in selected],
                }
            )
        if result.returncode or any(row["result"] != "PASS" for row in coverage_rows):
            issues.append("P9_COVERAGE_FAILED; retain coverage.xml/log")
    report = {
        "report_version": "p9-simulation-qualification.v1",
        "task_id": "TASK-P9-09",
        "implementation_sha": code,
        "result": "FAIL" if issues else "PASS",
        "observation_source": observation_source,
        "catalog_version": catalog_version,
        "independent_holdout": catalog_version == "v2" and not development_only,
        "mode": (
            "EXPOSED_V1_FAILURE_REGRESSION"
            if catalog_version == "v1"
            else "DEVELOPMENT_CALIBRATION"
            if development_only
            else "QUALIFICATION"
            if coverage
            else "RUNTIME_BENCHMARK_ONLY"
        ),
        "issues": issues,
        "catalog_sha256": catalog_hash,
        "coverage": coverage_rows,
        "coverage_scope": "fresh owner contract regression; generated real TCP/Redis/Worker samples are separate",
        "samples": {k: v["denominator"] for k, v in reports.items()},
        "environment": env,
        "reports": reports,
        "frozen_baseline": baseline,
        "recovery": recovery,
        "negative_results": negative_rows,
        "all_outcome_counts": dict(
            Counter(
                [
                    r["status"]
                    for v in reports.values()
                    for rows in v["samples"].values()
                    for r in rows
                ]
                + [r["status"] for r in negative_rows]
            )
        ),
        "boundaries": {
            "production": False,
            "capacity_sla_claim": False,
            "holdout_tuning": False,
            "kit_qualification": "P9-10",
        },
    }
    source_paths = [
        "backend/app/simulation/benchmarks/p9_catalog.py",
        "backend/tests/integration/p9_simulation_support.py",
        "scripts/p9_simulation_qualification.py",
        catalog_path(catalog_version),
        "fixtures/infeasible/P9-QUALIFICATION/negative-catalog.v1.json",
    ]
    report["source_files"] = {
        p: sha256((root / p).read_bytes()).hexdigest() for p in source_paths
    }
    report["working_tree_dirty"] = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    )
    observation_root = Path(observation_source) if observation_source else out
    wheel_identity = (
        observation_root.with_name(observation_root.name + "-installation")
        / "wheel-identity.json"
    )
    report["wheel_identity"] = (
        json.loads(wheel_identity.read_bytes()) if wheel_identity.exists() else None
    )
    write_new(out / "qualification-report.json", report)
    return report


def installed_run(
    root: Path,
    out: Path,
    broker: str,
    code: str,
    coverage: bool,
    development_only: bool = False,
    frozen_budget: Path | None = None,
    catalog_version: str = "v2",
) -> int:
    work = out.with_name(out.name + "-installation")
    work.mkdir(parents=True, exist_ok=False)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(work / "dist")],
        cwd=root,
        check=True,
    )
    (wheel,) = (work / "dist").glob("*.whl")
    env = work / "environment"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(env)], check=True
    )
    python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
        check=True,
    )
    args = [
        "--catalog-version",
        catalog_version,
        "--root",
        str(root),
        "--out",
        str(out),
        "--broker",
        broker,
        "--code-commit",
        code,
    ]
    if coverage:
        args.append("--coverage")
    if development_only:
        args.append("--development-only")
    if frozen_budget:
        args.extend(["--frozen-budget", str(frozen_budget)])
    bootstrap = work / "run.py"
    bootstrap.write_text(
        "import sys,pathlib,runpy\n"
        + f"sys.path.extend({[str(root), *site.getsitepackages()]!r})\n"
        + "import app,aps_extension_sdk\n"
        + f"prefix=pathlib.Path({str(env)!r}).resolve()\n"
        + "assert pathlib.Path(app.__file__).resolve().is_relative_to(prefix)\n"
        + "assert pathlib.Path(aps_extension_sdk.__file__).resolve().is_relative_to(prefix)\n"
        + f"sys.argv={[str(root / 'scripts/p9_simulation_qualification.py'), *args]!r}\n"
        + f'runpy.run_path({str(root / "scripts/p9_simulation_qualification.py")!r},run_name="__main__")\n',
        encoding="utf-8",
    )
    write_new(
        work / "wheel-identity.json",
        {
            "sha256": sha256(wheel.read_bytes()).hexdigest(),
            "wheel": wheel.name,
            "code_commit": code,
        },
    )
    return subprocess.run(
        [str(python), "-I", "-X", "utf8", str(bootstrap)], cwd=work
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--broker", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--development-only", action="store_true")
    parser.add_argument("--frozen-budget", type=Path)
    parser.add_argument("--catalog-version", choices=("v1", "v2"), default="v2")
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    frozen_budget = args.frozen_budget.resolve() if args.frozen_budget else None
    if args.installed:
        return installed_run(
            root,
            out,
            args.broker,
            args.code_commit,
            args.coverage,
            args.development_only,
            frozen_budget,
            args.catalog_version,
        )
    report = run(
        root,
        out,
        args.broker,
        args.code_commit,
        args.coverage,
        args.development_only,
        frozen_budget,
        args.catalog_version,
    )
    print(f"{report['result']} P9 simulation qualification")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
