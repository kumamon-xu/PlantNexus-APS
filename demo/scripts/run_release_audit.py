"""Assemble and verify the D18 versioned local release candidate."""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import TextIOWrapper
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, cast


for stream in (sys.stdout, sys.stderr):
    if isinstance(stream, TextIOWrapper):
        stream.reconfigure(encoding="utf-8", errors="replace")


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
VALIDATION_ROOT = DEMO_ROOT / "build" / "validation"
RELEASE_ROOT = DEMO_ROOT / "release"
DEFAULT_MANIFEST = RELEASE_ROOT / "cnc-demo-release-manifest.v1.json"
DEFAULT_REPORT = VALIDATION_ROOT / "release-audit-demo-10.json"
DIFF_BASE = "a9109e905fbc051666fcd3bc43322ae2c53e619d"
MANIFEST_VERSION = "cnc-demo-release-manifest.v1"
AUDIT_VERSION = "cnc-demo-release-audit.v1"
TASK_ID = "TASK-DEMO-10"
TARGET_SITE_STATUS = "PENDING_FINAL_SITE_REPLAY"
EXCLUDED_PARTS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".pyright",
        ".playwright-cli",
        "node_modules",
        "dist",
        "coverage",
        "playwright-report",
        "test-results",
    }
)
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "scripts"))

from plantnexus_demo.assets import load_demo_assets  # noqa: E402
from plantnexus_demo.delivery import (  # noqa: E402
    canonical_fingerprint,
    utc_now,
    verify_fingerprinted_document,
)
from run_delivery_rehearsal import verify_observation  # noqa: E402


class ReleaseAuditFailure(RuntimeError):
    """Stable release audit failure."""


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseAuditFailure("D18_RELEASE_DOCUMENT_INVALID") from error
    if not isinstance(document, dict):
        raise ReleaseAuditFailure("D18_RELEASE_DOCUMENT_INVALID")
    return cast(dict[str, Any], document)


def _excluded(relative: Path) -> bool:
    parts = relative.parts
    posix = relative.as_posix()
    return (
        any(part in EXCLUDED_PARTS for part in parts)
        or posix.startswith("runtime/")
        or posix.startswith("benchmarks/tmp/")
        or posix.startswith("data/generated/")
        or relative.suffix in {".pyc", ".pyo"}
        or relative.name.startswith("task-machine-report")
        or posix == "release/cnc-demo-release-manifest.v1.json"
        or posix == "build/validation/release-audit-demo-10.json"
    )


def _inventory() -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(DEMO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative_demo = path.relative_to(DEMO_ROOT)
        if _excluded(relative_demo):
            continue
        files.append(
            {
                "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return files


def _evidence_item(
    path: Path,
    *,
    fingerprint_field: str,
    version_field: str,
) -> dict[str, Any]:
    document = verify_fingerprinted_document(path, fingerprint_field)
    if document.get("status") != "PASS":
        raise ReleaseAuditFailure("D18_RELEASE_EVIDENCE_NOT_PASS")
    return {
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(path),
        "version": document.get(version_field),
        "fingerprint": document.get(fingerprint_field),
        "status": document.get("status"),
    }


def build_manifest() -> dict[str, Any]:
    assets = load_demo_assets()
    profile = assets.profile("showcase")
    protocol = _read_json(DEMO_ROOT / "benchmarks" / "formal-protocol.v1.json")
    baseline_path = (
        DEMO_ROOT
        / "benchmarks"
        / "baselines"
        / "cnc-demo-formal-benchmark.v1"
        / "baseline.json"
    )
    baseline = verify_fingerprinted_document(baseline_path, "baseline_fingerprint")
    observation_path = VALIDATION_ROOT / "delivery-observation-demo-10.json"
    verify_observation(observation_path)
    evidence = {
        "d16_e2e": _evidence_item(
            VALIDATION_ROOT / "e2e-evidence-demo-08.json",
            fingerprint_field="report_fingerprint",
            version_field="evidence_version",
        ),
        "d17_formal_benchmark": _evidence_item(
            VALIDATION_ROOT / "benchmark-evidence-demo-09.json",
            fingerprint_field="report_fingerprint",
            version_field="evidence_version",
        ),
        "d17_frozen_baseline": _evidence_item(
            baseline_path,
            fingerprint_field="baseline_fingerprint",
            version_field="baseline_version",
        ),
        "d18_delivery_observation": _evidence_item(
            observation_path,
            fingerprint_field="report_fingerprint",
            version_field="observation_version",
        ),
    }
    files = _inventory()
    document: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "release_id": "plantnexus-cnc-demo-0.1.0-demo.10",
        "task_id": TASK_ID,
        "generated_at_utc": utc_now(),
        "release_class": "LOCAL_DELIVERY_CANDIDATE",
        "target_site_status": TARGET_SITE_STATUS,
        "source": {
            "head": _git(["rev-parse", "HEAD"]).strip(),
            "diff_base": DIFF_BASE,
            "package_scope": "demo/**",
        },
        "entrypoints": {
            "windows": "demo/demo.ps1",
            "portable": "demo/demo.sh",
            "controller": "demo/scripts/democtl.py",
            "runbook": "demo/docs/D18-DEMO-RUNBOOK.md",
        },
        "scenario": {
            "profile_name": "showcase",
            "profile_id": profile.profile_id,
            "seed": profile.seed,
            "orders": profile.order_count,
            "operations": profile.operation_count,
            "resources": profile.resource_count,
            "horizon_days": profile.horizon_days,
            "initial_solve_seconds": profile.initial_solve_seconds,
            "replan_solve_seconds": profile.replan_solve_seconds,
            "profile_set_version": protocol["profile_set_version"],
            "parameter_freeze_status": baseline["parameter_freeze"]["status"],
        },
        "lock_identity": {
            "python": {
                "path": "uv.lock",
                "sha256": _sha256(REPOSITORY_ROOT / "uv.lock"),
            },
            "frontend": {
                "path": "demo/frontend/package-lock.json",
                "sha256": _sha256(DEMO_ROOT / "frontend" / "package-lock.json"),
            },
        },
        "evidence": evidence,
        "files": files,
        "file_count": len(files),
        "excluded_runtime_paths": [
            "demo/runtime/**",
            "demo/frontend/node_modules/**",
            "demo/frontend/dist/**",
            "demo/.playwright-cli/**",
            "demo/benchmarks/tmp/**",
            "demo/data/generated/**",
        ],
        "boundaries": {
            "loopback_only": True,
            "simulation_only": True,
            "synthetic_only": True,
            "production_authority": False,
            "draft_auto_published": False,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
            "p7_registration": None,
        },
    }
    document["manifest_fingerprint"] = canonical_fingerprint(document)
    return document


def verify_manifest(path: Path) -> dict[str, Any]:
    document = verify_fingerprinted_document(path, "manifest_fingerprint")
    expected_files = _inventory()
    files = document.get("files")
    baseline_path = (
        DEMO_ROOT
        / "benchmarks"
        / "baselines"
        / "cnc-demo-formal-benchmark.v1"
        / "baseline.json"
    )
    expected_evidence = {
        "d16_e2e": _evidence_item(
            VALIDATION_ROOT / "e2e-evidence-demo-08.json",
            fingerprint_field="report_fingerprint",
            version_field="evidence_version",
        ),
        "d17_formal_benchmark": _evidence_item(
            VALIDATION_ROOT / "benchmark-evidence-demo-09.json",
            fingerprint_field="report_fingerprint",
            version_field="evidence_version",
        ),
        "d17_frozen_baseline": _evidence_item(
            baseline_path,
            fingerprint_field="baseline_fingerprint",
            version_field="baseline_version",
        ),
        "d18_delivery_observation": _evidence_item(
            VALIDATION_ROOT / "delivery-observation-demo-10.json",
            fingerprint_field="report_fingerprint",
            version_field="observation_version",
        ),
    }
    expected_locks = {
        "python": {
            "path": "uv.lock",
            "sha256": _sha256(REPOSITORY_ROOT / "uv.lock"),
        },
        "frontend": {
            "path": "demo/frontend/package-lock.json",
            "sha256": _sha256(DEMO_ROOT / "frontend" / "package-lock.json"),
        },
    }
    if (
        document.get("manifest_version") != MANIFEST_VERSION
        or document.get("task_id") != TASK_ID
        or document.get("release_class") != "LOCAL_DELIVERY_CANDIDATE"
        or document.get("target_site_status") != TARGET_SITE_STATUS
        or not isinstance(files, list)
        or document.get("file_count") != len(files)
        or files != expected_files
        or document.get("evidence") != expected_evidence
        or document.get("lock_identity") != expected_locks
        or document.get("boundaries")
        != {
            "loopback_only": True,
            "simulation_only": True,
            "synthetic_only": True,
            "production_authority": False,
            "draft_auto_published": False,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
            "p7_registration": None,
        }
    ):
        raise ReleaseAuditFailure("D18_RELEASE_MANIFEST_INVALID")
    paths = [item.get("path") for item in files if isinstance(item, dict)]
    if len(paths) != len(set(paths)) or any(
        not isinstance(value, str) or not value.startswith("demo/") for value in paths
    ):
        raise ReleaseAuditFailure("D18_RELEASE_INVENTORY_SCOPE_INVALID")
    scenario = document.get("scenario")
    if not isinstance(scenario, dict) or scenario != {
        "profile_name": "showcase",
        "profile_id": "CNC-DEMO-SHOWCASE",
        "seed": 20260902,
        "orders": 132,
        "operations": 610,
        "resources": 24,
        "horizon_days": 10,
        "initial_solve_seconds": 20,
        "replan_solve_seconds": 30,
        "profile_set_version": "cnc-demo-benchmark-profiles.v2",
        "parameter_freeze_status": "FROZEN",
    }:
        raise ReleaseAuditFailure("D18_RELEASE_SCENARIO_INVALID")
    verify_observation(VALIDATION_ROOT / "delivery-observation-demo-10.json")
    return document


def _git(arguments: list[str]) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed git executable and read-only args
        [shutil.which("git") or "git", *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        creationflags=int(subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0,
    )
    if completed.returncode != 0:
        raise ReleaseAuditFailure("D18_RELEASE_GIT_QUERY_FAILED")
    return completed.stdout


def _workspace_changes() -> tuple[list[str], list[str]]:
    tracked = {
        line.strip().replace("\\", "/")
        for line in _git(["diff", "--name-only", DIFF_BASE, "--"]).splitlines()
        if line.strip()
    }
    untracked = {
        line.strip().replace("\\", "/")
        for line in _git(["ls-files", "--others", "--exclude-standard"]).splitlines()
        if line.strip()
    }
    changed = sorted(tracked | untracked)
    return (
        [path for path in changed if path == "demo" or path.startswith("demo/")],
        [path for path in changed if path != "demo" and not path.startswith("demo/")],
    )


def _documentation_checks() -> dict[str, bool]:
    runbook = (DEMO_ROOT / "docs" / "D18-DEMO-RUNBOOK.md").read_text(encoding="utf-8")
    acceptance = (DEMO_ROOT / "docs" / "05-benchmark-and-acceptance.md").read_text(
        encoding="utf-8"
    )
    script = (DEMO_ROOT / "docs" / "04-ux-and-demo-script.md").read_text(
        encoding="utf-8"
    )
    required_runbook = (
        ".\\demo\\demo.ps1 doctor",
        ".\\demo\\demo.ps1 start",
        ".\\demo\\demo.ps1 reset",
        ".\\demo\\demo.ps1 smoke",
        ".\\demo\\demo.ps1 stop",
        "132 单 / 610 道工序 / 24 台设备",
        "PENDING_FINAL_SITE_REPLAY",
        "不构成生产容量或 SLA",
    )
    return {
        "runbook_commands_complete": all(value in runbook for value in required_runbook),
        "acceptance_has_d18_gate": "D18 发布审计" in acceptance,
        "demo_script_has_day_of_run": "D18 现场运行" in script,
    }


def build_audit(manifest_path: Path) -> dict[str, Any]:
    manifest = verify_manifest(manifest_path)
    observation = verify_observation(VALIDATION_ROOT / "delivery-observation-demo-10.json")
    baseline = verify_fingerprinted_document(
        DEMO_ROOT
        / "benchmarks"
        / "baselines"
        / "cnc-demo-formal-benchmark.v1"
        / "baseline.json",
        "baseline_fingerprint",
    )
    e2e = verify_fingerprinted_document(
        VALIDATION_ROOT / "e2e-evidence-demo-08.json",
        "report_fingerprint",
    )
    d17_machine = _read_json(VALIDATION_ROOT / "task-machine-report-demo-09.json")
    demo_changes, external_changes = _workspace_changes()
    docs = _documentation_checks()
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    checks = {
        "release_manifest_fingerprint_pass": True,
        "release_inventory_exact": manifest["file_count"] == len(_inventory()),
        "delivery_observation_pass": observation["status"] == "PASS",
        "d16_e2e_pass": e2e["status"] == "PASS",
        "d17_parameter_freeze_pass": baseline["parameter_freeze"]["status"] == "FROZEN",
        "d17_closure_audit_fact_retained": (
            d17_machine.get("status") == "FAIL"
            and d17_machine.get("functional_status") == "PASS"
            and d17_machine.get("closure_blockers") == ["SCOPE_CHECK"]
        ),
        "showcase_profile_exact": manifest["scenario"]
        == {
            "profile_name": "showcase",
            "profile_id": "CNC-DEMO-SHOWCASE",
            "seed": 20260902,
            "orders": 132,
            "operations": 610,
            "resources": 24,
            "horizon_days": 10,
            "initial_solve_seconds": 20,
            "replan_solve_seconds": 30,
            "profile_set_version": "cnc-demo-benchmark-profiles.v2",
            "parameter_freeze_status": "FROZEN",
        },
        "entrypoints_present": all(
            (REPOSITORY_ROOT / path).is_file()
            for path in manifest["entrypoints"].values()
        ),
        "runbook_commands_complete": docs["runbook_commands_complete"],
        "acceptance_has_d18_gate": docs["acceptance_has_d18_gate"],
        "demo_script_has_day_of_run": docs["demo_script_has_day_of_run"],
        "package_scope_demo_only": all(
            item["path"].startswith("demo/") for item in manifest["files"]
        ),
        "shared_worktree_external_diffs_recorded": isinstance(external_changes, list),
        "source_commit_state_recorded": isinstance(demo_changes, list),
        "target_site_pending_recorded": manifest["target_site_status"]
        == TARGET_SITE_STATUS,
        "no_session_material_in_manifest": (
            "plantnexus_demo_session" not in serialized
            and "session.token" not in serialized
            and "Bearer " not in serialized
        ),
    }
    if not all(checks.values()):
        raise ReleaseAuditFailure("D18_RELEASE_ASSERTION_FAILED")
    source_commit_state = "UNCOMMITTED" if demo_changes else "COMMITTED"
    release_gate = (
        "PENDING_COMMIT_AND_TARGET_SITE_REPLAY"
        if demo_changes
        else "PENDING_TARGET_SITE_REPLAY"
    )
    document: dict[str, Any] = {
        "audit_version": AUDIT_VERSION,
        "task_id": TASK_ID,
        "generated_at_utc": utc_now(),
        "status": "PASS",
        "release_decision": "LOCAL_CANDIDATE_VERIFIED",
        "local_candidate_ready": True,
        "final_release_ready": False,
        "release_gate": release_gate,
        "target_site_status": TARGET_SITE_STATUS,
        "manifest": {
            "path": manifest_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(manifest_path),
            "fingerprint": manifest["manifest_fingerprint"],
            "file_count": manifest["file_count"],
        },
        "delivery_observation": {
            "path": "demo/build/validation/delivery-observation-demo-10.json",
            "fingerprint": observation["report_fingerprint"],
            "target_site_status": observation["target_site_status"],
        },
        "checks": checks,
        "workspace": {
            "diff_base": DIFF_BASE,
            "source_head": _git(["rev-parse", "HEAD"]).strip(),
            "source_commit_state": source_commit_state,
            "demo_change_count": len(demo_changes),
            "demo_changes": demo_changes,
            "external_change_count": len(external_changes),
            "external_changes": external_changes,
            "external_changes_in_release_inventory": [],
        },
        "boundaries": manifest["boundaries"],
    }
    document["report_fingerprint"] = canonical_fingerprint(document)
    return document


def verify_audit(report_path: Path, manifest_path: Path) -> dict[str, Any]:
    report = verify_fingerprinted_document(report_path, "report_fingerprint")
    manifest = verify_manifest(manifest_path)
    checks = report.get("checks")
    if (
        report.get("audit_version") != AUDIT_VERSION
        or report.get("task_id") != TASK_ID
        or report.get("status") != "PASS"
        or report.get("release_decision") != "LOCAL_CANDIDATE_VERIFIED"
        or report.get("local_candidate_ready") is not True
        or report.get("final_release_ready") is not False
        or report.get("target_site_status") != TARGET_SITE_STATUS
        or not isinstance(checks, dict)
        or len(checks) != 16
        or not all(checks.values())
        or report.get("manifest", {}).get("fingerprint")
        != manifest["manifest_fingerprint"]
        or report.get("manifest", {}).get("sha256") != _sha256(manifest_path)
    ):
        raise ReleaseAuditFailure("D18_RELEASE_AUDIT_INVALID")
    return report


def _bounded_output_path(path: Path, *, parent: Path, code: str) -> Path:
    resolved = path.resolve()
    if resolved.parent != parent.resolve():
        raise ReleaseAuditFailure(code)
    return resolved


def _write_exclusive(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ReleaseAuditFailure("D18_RELEASE_OUTPUT_ALREADY_EXISTS")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--assemble", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.assemble == arguments.verify_only:
        parser.error("exactly one of --assemble or --verify-only is required")
    try:
        manifest_path = _bounded_output_path(
            arguments.manifest,
            parent=RELEASE_ROOT,
            code="D18_RELEASE_MANIFEST_PATH_ESCAPE",
        )
        report_path = _bounded_output_path(
            arguments.report,
            parent=VALIDATION_ROOT,
            code="D18_RELEASE_REPORT_PATH_ESCAPE",
        )
        if arguments.assemble:
            manifest = build_manifest()
            _write_exclusive(manifest_path, manifest)
            try:
                report = build_audit(manifest_path)
                _write_exclusive(report_path, report)
            except Exception:
                manifest_path.unlink(missing_ok=True)
                raise
        else:
            report = verify_audit(report_path, manifest_path)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "message_zh": "D18 本地交付候选审计通过；最终现场机复放仍待完成",
                    "release_decision": report["release_decision"],
                    "release_gate": report["release_gate"],
                    "target_site_status": report["target_site_status"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    except ReleaseAuditFailure as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "code": str(error),
                    "message_zh": "D18 发布审计未通过",
                },
                ensure_ascii=False,
            )
        )
        return 1
    except Exception:  # noqa: BLE001 - never expose paths, traceback or session material
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "code": "D18_RELEASE_AUDIT_UNEXPECTED",
                    "message_zh": "D18 发布审计发生未分类错误，已隐藏内部细节",
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
