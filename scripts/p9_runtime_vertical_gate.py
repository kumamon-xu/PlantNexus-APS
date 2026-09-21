"""Independent audit of exact retained candidates; never builds product code."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import site
import subprocess
import sys
from typing import Any, cast
import xml.etree.ElementTree as ET

CANDIDATE_SHA = "2be5ac77da40b641c093e5ac1cc70caf2bd6caba"
KIT_SHA = "ed74471ab8252e6cf9da5845ba6e5382f7002a661535366f57e595027b1b974d"
RUNTIME_SHA = "7ab65e686bd68e8e30fa3588321c278a900c8bc8e4c77d9e71d0934fc4695180"


RETAINED_CANDIDATE = {
    "contract": "p9-audit-candidate.v1",
    "source_revision": CANDIDATE_SHA,
    "runtime_version": "0.2.0",
    "kit_version": "1.1.0",
    "runtime_sha256": RUNTIME_SHA,
    "kit_sha256": KIT_SHA,
}


def candidate_identity(path: Path | None, code: str) -> dict[str, str]:
    if path is None:
        return dict(RETAINED_CANDIDATE)
    value = json.loads(path.read_bytes())
    if (
        not isinstance(value, dict)
        or set(value) != set(RETAINED_CANDIDATE)
        or value.get("contract") != "p9-audit-candidate.v1"
        or value.get("source_revision") != code
        or re.fullmatch(r"[0-9a-f]{40}", code) is None
        or (value.get("runtime_version"), value.get("kit_version"))
        != ("0.2.1", "1.1.1")
        or any(
            not isinstance(value.get(k), str)
            or re.fullmatch(r"[0-9a-f]{64}", value[k]) is None
            for k in ("runtime_sha256", "kit_sha256")
        )
    ):
        raise ValueError("P9_CORRECTIVE_CANDIDATE_IDENTITY_INVALID")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def operations(
    openapi: dict[str, Any], observations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """A route inventory is not behavioral evidence; preserve missing polarity."""
    rows = []
    for path, methods in sorted(openapi["paths"].items()):
        for method, operation in methods.items():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            pattern = re.sub(r"\{[^}]+\}", "[^/]+", path)
            selected = [
                r
                for r in observations
                if r["method"] == method.upper() and re.fullmatch(pattern, r["path"])
            ]
            positive = [r for r in selected if 200 <= r["status"] < 300]
            negative = [
                r
                for r in selected
                if 400 <= r["status"] < 600
                and "test_empty_unauthenticated_requests" not in r["test_id"]
            ]
            # Liveness has no dependency or identity gate; readiness does.
            required_negative = path != "/health/live"
            undeclared = sorted(
                {str(r["status"]) for r in selected}
                - set(operation.get("responses", {}))
            )
            rows.append(
                {
                    "operation_id": operation["operationId"],
                    "method": method,
                    "path": path,
                    "positive_count": len(positive),
                    "negative_count": len(negative),
                    "negative_required": required_negative,
                    "status": "PASS"
                    if positive and (negative or not required_negative)
                    else "NOT_RUN",
                    "undeclared_statuses": undeclared,
                    "test_ids": sorted({r["test_id"] for r in selected}),
                }
            )
    if len(rows) != 34 or len({r["operation_id"] for r in rows}) != 34:
        raise ValueError("P9_OPERATION_INVENTORY_MISMATCH")
    return rows


class TracePlugin:
    """Observe HTTP responses only; never replace a business implementation."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.current = "session"
        self.original: Any = None

    def pytest_runtest_setup(self, item: Any) -> None:
        self.current = item.nodeid

    def pytest_sessionstart(self, session: Any) -> None:
        import httpx

        self.original = httpx.Client.send
        original = self.original

        def send(client: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
            response = original(client, request, *args, **kwargs)
            self.rows.append(
                {
                    "test_id": self.current,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                }
            )
            return response

        setattr(httpx.Client, "send", send)

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        import httpx

        httpx.Client.send = self.original


def installed(
    root: Path, out: Path, broker: str, code: str, candidate: dict[str, str]
) -> None:
    import app
    import aps_extension_sdk
    import aps_extension_tooling
    import pytest
    from app.api.app import create_app
    from app.infrastructure.config import Settings
    from scripts.p9_simulation_qualification import run as qualify

    for module in (app, aps_extension_sdk, aps_extension_tooling):
        if (
            not Path(module.__file__ or "")
            .resolve()
            .is_relative_to(Path(sys.prefix).resolve())
        ):
            raise ValueError("P9_PRODUCT_IMPORT_ESCAPED_INSTALLED_ENVIRONMENT")
    if (
        app.RUNTIME_VERSION != candidate["runtime_version"]
        or app.SCHEMA_VERSION != "2.11.0"
    ):
        raise ValueError("P9_INSTALLED_IDENTITY_MISMATCH")
    write(
        out / "installed-identity.json",
        {
            "runtime": app.RUNTIME_VERSION,
            "schema": app.SCHEMA_VERSION,
            "source_revision": candidate["source_revision"],
            "audit_revision": code,
            "prefix": sys.prefix,
            "app_path": app.__file__,
            "sdk_path": aps_extension_sdk.__file__,
        },
    )
    catalog = json.loads(
        (root / "fixtures/synthetic/P9-QUALIFICATION/catalog.v2.json").read_bytes()
    )
    paths = sorted(
        {p for group in catalog["coverage"].values() for p in group}
        | {
            "backend/tests/integration/test_p9_vertical_install.py",
            "backend/tests/integration/test_p9_delivery_install.py",
            "backend/tests/integration/test_p8_runtime_composition.py",
            "backend/tests/integration/test_p8_headless_http_api_integration.py",
        }
    )
    if candidate["runtime_version"] == "0.2.1":
        paths.append("backend/tests/integration/test_p9_vertical_corrective.py")
    plugin = TracePlugin()
    result = pytest.main(
        [
            "-q",
            "-o",
            "pythonpath=",
            "-k",
            "not browser",
            "--junitxml=" + str(out / "fresh-contracts.xml"),
            *[str(root / p) for p in paths],
        ],
        plugins=[plugin],
    )
    write(out / "http-observations.json", plugin.rows)
    document = create_app(
        Settings(runtime_schema_directory=root / "schemas/json"), probes={}
    ).openapi()
    write(out / "openapi.json", document)
    formal_files = {
        "test_p9_manual.py",
        "test_p9_readmodel.py",
        "test_p9_events.py",
        "test_p9_replan.py",
        "test_p9_consumers.py",
        "test_p9_vertical_install.py",
        "test_p9_vertical_corrective.py",
        "test_p8_headless_http_api_integration.py",
        "test_p8_runtime_composition.py",
    }
    formal_rows = [
        r for r in plugin.rows if Path(r["test_id"].split("::")[0]).name in formal_files
    ]
    write(out / "operation-coverage.json", operations(document, formal_rows))
    tree = ET.parse(out / "fresh-contracts.xml").getroot()
    cases = tree.findall(".//testcase")
    coverage = []
    for cell, sources in catalog["coverage"].items():
        prefixes = {p.removesuffix(".py").replace("/", ".") for p in sources}
        selected = [c for c in cases if c.get("classname") in prefixes]
        ok = bool(selected) and all(
            not any(c.find(t) is not None for t in ("failure", "error", "skipped"))
            for c in selected
        )
        coverage.append(
            {
                "cell": cell,
                "status": "PASS" if ok else "FAIL",
                "tests": len(selected),
                "sources": sources,
            }
        )
    write(
        out / "fresh-contracts.json",
        {
            "status": "PASS"
            if result == 0 and not tree.findall(".//skipped")
            else "FAIL",
            "tests": len(cases),
            "failures": len(tree.findall(".//failure")),
            "errors": len(tree.findall(".//error")),
            "skipped": len(tree.findall(".//skipped")),
            "coverage": coverage,
            "source_files": {
                p: sha256((root / p).read_bytes()).hexdigest() for p in paths
            },
        },
    )
    # A new environment calibrates development first under the frozen v2 policy;
    # the sealed holdout never influences that budget. Uses installed product.
    qualify(
        root,
        out / "qualification",
        broker,
        candidate["source_revision"],
        False,
        catalog_version="v2",
    )


def verdict(checks: list[dict[str, Any]], code: str) -> dict[str, Any]:
    gaps = [
        {
            "blocker_id": "P9-GAP-" + str(index + 1).zfill(3),
            "summary": row["summary"],
            "check_id": row["check_id"],
        }
        for index, row in enumerate(checks)
        if row["status"] == "BLOCKED"
    ]
    counts = Counter(row["status"] for row in checks)
    if set(counts) - {"PASS", "BLOCKED"}:
        raise ValueError("P9_INVALID_AUDIT_CHECK")
    return {
        "report_version": "p9-runtime-vertical-gate.v1",
        "task_id": "TASK-P9-11",
        "code_commit": code,
        "validation_profile": "PHASE_GATE",
        "audit_status": "PASS",
        "verdict": "NOT_READY" if gaps else "READY",
        "issues": [],
        "blocking_gaps": gaps,
        "checks": checks,
        "check_summary": {
            "check_count": len(checks),
            "pass_count": counts["PASS"],
            "blocked_count": counts["BLOCKED"],
            "error_count": 0,
        },
    }


def audit(
    root: Path,
    out: Path,
    kit: Path,
    runtime: Path,
    broker: str,
    code: str,
    identity_path: Path | None = None,
    *,
    retained_exit: bool = False,
) -> dict[str, Any]:
    from aps_developer_kit.check import _clean_install_and_cli
    from aps_developer_kit.contracts import verify_kit_archive
    from app.infrastructure.release.contracts import verify_release_archive

    if retained_exit:
        from scripts.p9_exit_gate_audit import EXIT_CANDIDATE

        if identity_path is not None:
            raise ValueError("P9_EXIT_IDENTITY_OVERRIDE_FORBIDDEN")
        candidate = dict(EXIT_CANDIDATE)
    else:
        candidate = candidate_identity(identity_path, code)
    out.mkdir(parents=True, exist_ok=False)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if head != code:
        raise ValueError("P9_AUDIT_REVISION_MISMATCH")
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, text=True
        ).strip()
    )
    write(
        out / "audit-input.json",
        {
            "audit_revision": code,
            "working_tree_dirty": dirty,
            "candidate_revision": candidate["source_revision"],
            "candidate_identity": candidate,
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    )
    if (
        sha256(kit.read_bytes()).hexdigest() != candidate["kit_sha256"]
        or sha256(runtime.read_bytes()).hexdigest() != candidate["runtime_sha256"]
    ):
        raise ValueError("P9_RETAINED_CANDIDATE_DIGEST_MISMATCH")
    k = verify_kit_archive(
        kit,
        expected_kit_version=candidate["kit_version"],
        expected_code_commit=candidate["source_revision"],
    )
    r = verify_release_archive(
        runtime,
        expected_runtime_version=candidate["runtime_version"],
        expected_code_commit=candidate["source_revision"],
    )
    if (
        k.runtime_release_fingerprint != r.release_fingerprint
        or k.files[cast(Any, k.lock)["artifacts"]["runtime"]["path"]]
        != runtime.read_bytes()
    ):
        raise ValueError("P9_NESTED_CANDIDATE_MISMATCH")

    for name, raw in r.files.items():
        if name.startswith("runtime/schemas/json/"):
            source = root / name.removeprefix("runtime/")
            if not source.is_file() or source.read_bytes() != raw:
                raise ValueError("P9_SCHEMA_DRIVER_DIFFERS_FROM_CANDIDATE")

    def consume(python: Path, kit_root: Path) -> None:
        bootstrap = out / "installed-driver.py"
        bootstrap.write_text(
            "import sys,os,pathlib,json\n"
            + f"sys.path.extend({[str(root), *site.getsitepackages()]!r})\n"
            + f"m=json.loads(pathlib.Path({str(kit_root / 'metadata/developer-kit-manifest.json')!r}).read_bytes())\n"
            + "os.environ['PLANTNEXUS_DEVELOPER_KIT_VERSION']=m['kit_version']\n"
            + "os.environ['PLANTNEXUS_DEVELOPER_KIT_FINGERPRINT']=m['release_fingerprint']\n"
            + "from scripts.p9_runtime_vertical_gate import installed\n"
            + f"installed(pathlib.Path({str(root)!r}),pathlib.Path({str(out)!r}),{broker!r},{code!r},{candidate!r})\n"
            + (
                "from scripts.p9_exit_gate_audit import installed_boundaries\n"
                + f"installed_boundaries(pathlib.Path({str(out)!r}))\n"
                if retained_exit
                else ""
            ),
            encoding="utf-8",
            newline="\n",
        )
        with (out / "installed.log").open("x", encoding="utf-8") as log:
            subprocess.run(
                [str(python), "-I", str(bootstrap)],
                cwd=kit_root,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=1800,
            )

    _clean_install_and_cli(
        kit,
        clean_projects=True,
        conformance_report=out / "conformance.json",
        installed_check=consume,
    )
    contracts = json.loads((out / "fresh-contracts.json").read_bytes())
    q = json.loads((out / "qualification/qualification-report.json").read_bytes())
    rows = json.loads((out / "operation-coverage.json").read_bytes())
    checks = []

    def check(identity: str, ok: bool, summary: str) -> None:
        checks.append(
            {
                "check_id": identity,
                "status": "PASS" if ok else "BLOCKED",
                "summary": summary,
            }
        )

    check(
        "candidate",
        True,
        f"Exact retained Runtime {candidate['runtime_version']} / Kit {candidate['kit_version']} installed; two independent extensions conform.",
    )
    check(
        "fresh-contracts",
        contracts["status"] == "PASS",
        "Fresh installed contract and fault replay must have zero failure/error/skip.",
    )
    for cell in contracts["coverage"]:
        check(
            cell["cell"],
            cell["status"] == "PASS",
            f"{cell['cell']} fresh owner regression: {cell['tests']} tests; separate TCP/Redis qualification below.",
        )
    check(
        "sealed-holdout",
        q["result"] == "PASS" and q["samples"] == {"development": 9, "holdout": 9},
        "Fresh v2 XS/S/M real TCP/Redis/Worker/Validator/publication/export; frozen development budget then sealed holdout.",
    )
    for row in rows:
        check(
            row["operation_id"],
            row["status"] == "PASS",
            f"{row['operation_id']}: positive={row['positive_count']}, negative={row['negative_count']}; missing polarity remains NOT_RUN.",
        )
    readiness = next(r for r in rows if r["path"] == "/health/ready")
    check(
        "readiness-contract",
        "503" not in readiness["undeclared_statuses"],
        "Observed readiness 503 must be declared by the candidate OpenAPI contract.",
    )
    report = verdict(checks, code)
    if identity_path is not None:
        report["task_id"] = "TASK-P9-13"
    report["audit_working_tree_dirty"] = dirty
    report.update(
        candidate={
            "source_revision": candidate["source_revision"],
            "runtime_sha256": candidate["runtime_sha256"],
            "kit_sha256": candidate["kit_sha256"],
            "runtime_version": candidate["runtime_version"],
            "kit_version": candidate["kit_version"],
        },
        fresh={
            "contract_tests": contracts["tests"],
            "operation_rows": rows,
            "samples": q["samples"],
            "outcomes": q["all_outcome_counts"],
        },
        boundaries={
            "production": False,
            "product_changes": False,
            "phase_exit": False,
            "frontend": (
                "Current SHA requires Frontend regression; generated OpenAPI identity updated without UI behavior changes"
                if identity_path is not None
                else "P9-10 exact Provider browser evidence reused; no frontend changes"
            ),
            "owner_fault_tests": "Installed product; explicit identity, clock and controlled fault injection; not all use a real broker",
        },
    )
    report["evidence"] = {
        str(p.relative_to(out)).replace("\\", "/"): sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.suffix in {".json", ".xml", ".log", ".py"}
    }
    write(out / "gate.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--candidate-identity", type=Path)
    parser.add_argument("--broker", required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    result = audit(
        args.root.resolve(),
        args.out.resolve(),
        args.kit.resolve(),
        args.runtime.resolve(),
        args.broker,
        args.code_commit,
        args.candidate_identity,
    )
    print(
        json.dumps(
            {
                "audit_status": result["audit_status"],
                "verdict": result["verdict"],
                "checks": result["check_summary"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
