"""Dependency-free acceptance evidence gate used by required CI aggregation."""

import re

CHECKS = (
    "clean-store-offline",
    "install",
    "repeat-migration",
    "identity",
    "tls-health",
    "headless-chain",
    "input-and-identity-negatives",
    "workspace-read-approve-publish-export",
    "capability-scope-audit",
    "formal-validator",
    "config-kit-extension-negatives",
    "restart-persistence",
    "backup-restore",
    "same-version-rollback",
    "canary",
)


def validate(value, bundle, commit):
    def require(ok):
        if not ok:
            raise ValueError("invalid clean acceptance evidence")

    require(value.get("schema_version") == "enterprise-clean-acceptance.v1")
    require(value.get("task_id") == "TASK-P8-28" and value.get("code_commit") == commit)
    require(
        value.get("status") == "PASS"
        and value.get("verdict") == "READY"
        and value.get("development") is False
        and value.get("production_ready") is False
    )
    require(
        value.get("issues") == []
        and bundle.get("status") == "PASS"
        and bundle.get("code_commit") == commit
    )
    candidate = value.get("candidate", {})
    require(candidate.get("packaging_commit") == commit)
    for key in (
        "archive_sha256",
        "payload_fingerprint",
        "manifest_sha256",
        "checksums_sha256",
    ):
        require(
            re.fullmatch(r"[0-9a-f]{64}", candidate.get(key, ""))
            and candidate[key] == bundle.get(key)
        )
    require(
        candidate.get("images") == bundle.get("images")
        and set(candidate.get("images", {})) == {"runtime", "database", "redis"}
    )
    expected = {
        mode + "-" + check for mode in ("standalone", "enterprise") for check in CHECKS
    }
    checks = value.get("checks", [])
    require(
        len(checks) == len(expected)
        and value.get("expected_check_count") == len(expected)
    )
    require(
        {c.get("name") for c in checks} == expected
        and all(c.get("status") == "PASS" for c in checks)
    )
    by_name = {c["name"]: c for c in checks}
    for mode in ("standalone", "enterprise"):
        clean = by_name[mode + "-clean-store-offline"]
        require(
            clean.get("initial_images") == 0
            and clean.get("host_python") is False
            and clean.get("checkout") is False
            and clean.get("network") == "none"
            and clean.get("engine") == "27.5.1"
        )
        require(by_name[mode + "-tls-health"].get("certificate_verified") is True)
        require(by_name[mode + "-headless-chain"].get("state") == "COMPLETED")
        require(by_name[mode + "-formal-validator"].get("negative_rejected") is True)
        require(
            by_name[mode + "-workspace-read-approve-publish-export"].get(
                "schedule_state"
            )
            == "PUBLISHED"
        )
    require(bool(value.get("commands")))
