"""Fresh P9 Exit against the immutable P9-13 candidate, not a rebuilt product."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from scripts.p9_runtime_vertical_gate import audit, verdict, write

EXIT_CANDIDATE = {
    "contract": "p9-audit-candidate.v1",
    "source_revision": "640f123ac27bf3e818675db5b44edb66b4967ab4",
    "runtime_version": "0.2.1",
    "kit_version": "1.1.1",
    "runtime_sha256": "61556443f9c2dfb8fd70bd6b854bec03da0540e6986e2841b2a8aa11e9e7d748",
    "kit_sha256": "ba55804f9ea30379900b5fb23262c500ca6d0ec28eb51985ffc13f2bc71a144a",
}
BLOCKED_CAPABILITIES = (
    "SECONDARY_CAPACITY",
    "SEQUENCE_DEPENDENT_SETUP",
    "BATCH_PROCESSING",
    "SPLIT_MERGE",
    "MATERIAL_COMPETITION",
    "PREEMPTIVE_OPERATION",
    "BUFFER_CAPACITY",
    "ALTERNATIVE_MATERIAL",
    "MULTI_FACTORY",
    "AI_DURATION_PREDICTION",
    "REALITY_CALIBRATION",
)
PROTECTED_INPUTS = (
    "backend/app",
    "backend/aps_extension_sdk",
    "backend/aps_extension_tooling",
    "backend/aps_developer_kit",
    "backend/migrations",
    "frontend",
    "schemas",
    "fixtures",
    "benchmarks",
    "pyproject.toml",
    "uv.lock",
    "infra/release",
    "scripts/p9_simulation_qualification.py",
)


def installed_boundaries(out: Path) -> None:
    """Independent installed-registry rejection, separate from HTTP coverage."""
    from app.domain.capabilities import (
        CAPABILITY_STATUS_BY_NAME,
        CapabilityContractError,
        CapabilityName,
        require_v1_capability_contract,
    )

    rows = []
    for name in BLOCKED_CAPABILITIES:
        error = None
        try:
            require_v1_capability_contract(["DAG_ROUTING", name])
        except CapabilityContractError as exc:
            error = exc.code.value
        status = CAPABILITY_STATUS_BY_NAME[CapabilityName(name)].value
        rows.append(
            {
                "capability": name,
                "registry_status": status,
                "error": error,
                "status": "PASS"
                if error == "UNSUPPORTED_CAPABILITY"
                and status in {"UNSUPPORTED", "DEFERRED"}
                else "BLOCKED",
            }
        )
    write(out / "exit-capabilities.json", {"checks": rows})


def frozen_inputs(root: Path) -> dict[str, Any]:
    changed = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            EXIT_CANDIDATE["source_revision"],
            "--",
            *PROTECTED_INPUTS,
        ],
        cwd=root,
        text=True,
    ).splitlines()
    return {
        "status": "PASS" if not changed else "BLOCKED",
        "changed": changed,
        "candidate_revision": EXIT_CANDIDATE["source_revision"],
        "protected_inputs": list(PROTECTED_INPUTS),
    }


def exit_report(
    vertical: dict[str, Any],
    capabilities: dict[str, Any],
    frozen: dict[str, Any],
    code: str,
) -> dict[str, Any]:
    """Do not infer readiness from a predecessor's or producer's verdict."""
    expected = {k: v for k, v in EXIT_CANDIDATE.items() if k != "contract"}
    if (
        vertical.get("code_commit") != code
        or vertical.get("candidate") != expected
        or vertical.get("audit_status") != "PASS"
        or vertical.get("issues")
        or vertical.get("audit_working_tree_dirty") is not False
    ):
        raise ValueError("P9_EXIT_FRESH_IDENTITY_INVALID")
    checks = vertical["checks"]
    required = {"candidate", "fresh-contracts", "sealed-holdout", "readiness-contract"}
    required.update(f"B{i:02}" for i in range(1, 11))
    rows = vertical["fresh"]["operation_rows"]
    required.update(r["operation_id"] for r in rows)
    if (
        len(checks) != 48
        or len(rows) != 34
        or len(required) != 48
        or {c["check_id"] for c in checks} != required
        or vertical["check_summary"] != verdict(checks, code)["check_summary"]
    ):
        raise ValueError("P9_EXIT_COVERAGE_INCOMPLETE")
    caps = capabilities["checks"]
    if len(caps) != len(BLOCKED_CAPABILITIES) or {c["capability"] for c in caps} != set(
        BLOCKED_CAPABILITIES
    ):
        raise ValueError("P9_EXIT_CAPABILITY_COVERAGE_INCOMPLETE")
    additional = [
        {
            "check_id": "frozen-product-inputs",
            "status": frozen["status"],
            "summary": "Product, Schema, dependencies, fixtures and frozen budgets unchanged.",
        }
    ]
    for row in caps:
        ok = row["error"] == "UNSUPPORTED_CAPABILITY" and row["registry_status"] in {
            "UNSUPPORTED",
            "DEFERRED",
        }
        additional.append(
            {
                "check_id": row["capability"],
                "status": "PASS" if ok else "BLOCKED",
                "summary": "Installed declaration precheck must reject future/deferred capability.",
            }
        )
    report = verdict([*checks, *additional], code)
    report.update(
        report_version="p9-exit-gate.v1",
        task_id="TASK-P9-12",
        candidate=expected,
        fresh=vertical["fresh"],
        audit_working_tree_dirty=False,
        boundaries={
            "production": False,
            "phase_transition": False,
            "external_release": False,
            "real_calibration": False,
            "manual_export": "Reject incompatible Solution/KPI lineage",
            "extension_search_contribution": "Not implemented; P11",
            "scale": "Frozen synthetic XS/S/M only",
        },
    )
    return report


def run(
    root: Path, out: Path, kit: Path, runtime: Path, broker: str, code: str
) -> dict[str, Any]:
    frozen = frozen_inputs(root)
    if frozen["status"] != "PASS":
        raise ValueError("P9_EXIT_PRODUCT_CHANGED_REQUIRES_NEW_CORRECTIVE")
    vertical = audit(
        root, out / "fresh", kit, runtime, broker, code, retained_exit=True
    )
    capabilities = json.loads((out / "fresh/exit-capabilities.json").read_bytes())
    report = exit_report(vertical, capabilities, frozen, code)
    write(out / "frozen-inputs.json", frozen)
    report["runner_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    report["evidence"] = {
        p.relative_to(out).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }
    write(out / "exit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--broker", required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    report = run(
        args.root.resolve(),
        args.out.resolve(),
        args.kit.resolve(),
        args.runtime.resolve(),
        args.broker,
        args.code_commit,
    )
    print(json.dumps({k: report[k] for k in ("verdict", "check_summary")}))
    return 0 if report["verdict"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
