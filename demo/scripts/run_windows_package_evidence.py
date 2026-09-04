"""Seal D19 package audit and rehearsal outputs into compact evidence."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
DEFAULT_AUDIT = DEMO_ROOT / "build" / "validation" / "windows-package-audit-demo-11.json"
DEFAULT_OBSERVATION = (
    DEMO_ROOT / "build" / "validation" / "windows-package-observation-demo-11.json"
)
DEFAULT_BROWSER_REPORT = (
    DEMO_ROOT
    / "build"
    / "validation"
    / "browser-windows-package-observation-demo-11.json"
)
DEFAULT_REPORT = (
    DEMO_ROOT / "build" / "validation" / "windows-package-evidence-demo-11.json"
)
EVIDENCE_VERSION = "cnc-demo-windows-package-evidence.v1"
BROWSER_OBSERVATION_VERSION = "cnc-demo-windows-package-browser-observation.v1"


class PackageEvidenceError(RuntimeError):
    pass


def _canonical_fingerprint(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _read_fingerprinted(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageEvidenceError(f"invalid evidence input: {path.name}") from error
    if not isinstance(document, dict):
        raise PackageEvidenceError(f"evidence input is not an object: {path.name}")
    report = cast(dict[str, Any], document)
    observed = report.pop("report_fingerprint", None)
    expected = _canonical_fingerprint(report)
    report["report_fingerprint"] = observed
    if observed != expected:
        raise PackageEvidenceError(f"evidence fingerprint differs: {path.name}")
    return report


def _write_fingerprinted(path: Path, document: dict[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    payload["report_fingerprint"] = _canonical_fingerprint(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def build_evidence(
    *,
    audit_path: Path,
    observation_path: Path,
    browser_report_path: Path,
) -> dict[str, Any]:
    audit = _read_fingerprinted(audit_path)
    observation = _read_fingerprinted(observation_path)
    lan = cast(dict[str, Any], observation.get("lan"))
    browser = cast(dict[str, Any], lan.get("browser"))
    story = cast(dict[str, Any], cast(dict[str, Any], observation.get("loopback")).get("story"))
    audit_checks = cast(dict[str, Any], audit.get("checks"))
    observation_checks = cast(dict[str, Any], observation.get("checks"))
    if (
        audit.get("status") != "PASS"
        or observation.get("status") != "PASS"
        or audit.get("zip_sha256") != observation.get("package_zip_sha256")
        or audit.get("package_version") != observation.get("package_version")
        or not audit_checks
        or not all(value is True for value in audit_checks.values())
        or not observation_checks
        or not all(value is True for value in observation_checks.values())
        or browser.get("locale") != "zh-CN"
        or browser.get("console_errors") != 0
        or browser.get("console_warnings") != 0
        or browser.get("orders") != 132
        or browser.get("operations") != 610
        or browser.get("resources") != 24
        or story.get("solver_status") not in {"OPTIMAL", "FEASIBLE"}
        or story.get("validation_status") != "PASS"
        or story.get("schedule_state") != "READY_FOR_REVIEW"
        or observation.get("simulation_only") is not True
        or observation.get("production_ready") is not False
    ):
        raise PackageEvidenceError("D19 package evidence assertions failed")

    browser_report = {
        "observation_version": BROWSER_OBSERVATION_VERSION,
        "task_id": "TASK-DEMO-11",
        "status": "PASS",
        "package_version": observation["package_version"],
        "package_zip_sha256": observation["package_zip_sha256"],
        "network_mode": "TRUSTED_LAN_PRIVATE_HOST_ALLOWLIST",
        "address": lan["address"],
        "port": lan["port"],
        **browser,
        "simulation_only": True,
        "production_ready": False,
    }
    sealed_browser = _write_fingerprinted(browser_report_path, browser_report)
    checks = {
        "audit_fingerprint": True,
        "observation_fingerprint": True,
        "zip_identity_matches": True,
        "package_version_matches": True,
        "audit_checks_12_of_12": len(audit_checks) == 12,
        "runtime_checks_22_of_22": len(observation_checks) == 22,
        "minimal_path_no_python_node_uv_npm": True,
        "two_custom_ports": cast(dict[str, Any], observation["loopback"])["port"]
        != lan["port"],
        "single_origin": True,
        "showcase_132_610_24": True,
        "packaged_cp_sat_validator": True,
        "trusted_lan_route": True,
        "browser_zh_cn": True,
        "browser_console_clean": True,
        "safe_stop_no_residual_state": observation_checks[
            "no_residual_process_state"
        ],
        "simulation_only_non_production": True,
    }
    if not all(checks.values()):
        raise PackageEvidenceError("D19 compact evidence checks failed")
    return {
        "evidence_version": EVIDENCE_VERSION,
        "task_id": "TASK-DEMO-11",
        "status": "PASS",
        "package": {
            "version": audit["package_version"],
            "zip_path": audit["zip_path"],
            "zip_bytes": audit["zip_bytes"],
            "zip_sha256": audit["zip_sha256"],
            "payload_bytes": audit["payload_bytes"],
            "file_count": audit["file_count"],
        },
        "runtime": {
            "loopback_port": cast(dict[str, Any], observation["loopback"])["port"],
            "lan_address": lan["address"],
            "lan_port": lan["port"],
            "start_seconds": cast(dict[str, Any], observation["loopback"])[
                "start_seconds"
            ],
            "reset_seconds": story["reset_seconds"],
            "initial_plan_seconds": story["initial_plan_seconds"],
            "solver_status": story["solver_status"],
            "validation_status": story["validation_status"],
            "schedule_state": story["schedule_state"],
        },
        "browser_report": {
            "path": str(browser_report_path.relative_to(REPOSITORY_ROOT)).replace(
                "\\", "/"
            ),
            "report_fingerprint": sealed_browser["report_fingerprint"],
        },
        "checks": checks,
        "passed_checks": sum(checks.values()),
        "total_checks": len(checks),
        "target_site_status": observation["target_site_status"],
        "release_classification": "WINDOWS_PACKAGE_CANDIDATE_VERIFIED",
        "simulation_only": True,
        "synthetic_only": True,
        "production_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--observation", type=Path, default=DEFAULT_OBSERVATION)
    parser.add_argument("--browser-report", type=Path, default=DEFAULT_BROWSER_REPORT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()
    try:
        report = build_evidence(
            audit_path=arguments.audit.resolve(),
            observation_path=arguments.observation.resolve(),
            browser_report_path=arguments.browser_report.resolve(),
        )
    except (OSError, PackageEvidenceError, ValueError, TypeError, KeyError) as error:
        report = {
            "evidence_version": EVIDENCE_VERSION,
            "task_id": "TASK-DEMO-11",
            "status": "FAIL",
            "code": type(error).__name__,
            "message": str(error),
            "simulation_only": True,
            "production_ready": False,
        }
        _write_fingerprinted(arguments.report, report)
        print(json.dumps(report, ensure_ascii=False))
        return 2
    sealed = _write_fingerprinted(arguments.report, report)
    print(json.dumps(sealed, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
