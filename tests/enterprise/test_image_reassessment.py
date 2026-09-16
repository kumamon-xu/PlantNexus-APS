"""A precise metadata refresh retains risk and cannot authorize new or fixable CVEs."""

import json

import pytest

from scripts import enterprise_image_build as image


@pytest.fixture
def inputs():
    policy = json.loads((image.ROOT / "infra/enterprise/image-security-policy.v1.json").read_text())
    reassessment = json.loads(
        (image.ROOT / "infra/enterprise/image-security-reassessment.v1.json").read_text()
    )
    scan = {
        "scanner_image": reassessment["scanner_image"],
        "vulnerabilities": [{
            "class": "os-pkgs", "VulnerabilityID": "CVE-2026-75803", "PkgName": package,
            "InstalledVersion": "3.0.20-1~deb12u2", "Severity": "MEDIUM", "Status": "affected",
        } for package in ("libssl3", "openssl")],
    }
    return scan, policy, reassessment


def test_exact_refresh_retains_both_unresolved_findings(inputs):
    scan, policy, reassessment = inputs
    result = image.assess_security(scan, policy, os_reassessment=reassessment)
    assert result["production_security_approval"] is False
    assert result["upstream_os_raw_count"] == 2
    assert result["upstream_os_unique_count"] == 1
    assert result["os_component_vex"] == []
    assert {v["package"] for v in result["os_reassessed_unresolved_findings"]} == {"libssl3", "openssl"}
    assert all(v["severity"] == "MEDIUM" and v["status"] == "UNRESOLVED_INTERNAL_TEST_SIMULATION_ONLY"
               for v in result["os_reassessed_unresolved_findings"])
    for finding in scan["vulnerabilities"]:
        assert any(v["id"] == finding["VulnerabilityID"] and v["package"] == finding["PkgName"]
                   and v["version"] == finding["InstalledVersion"] and v["severity"] == "LOW"
                   and v["vendor_status"] == "affected" for v in policy["unresolved_os_findings"])


def test_old_policy_alone_still_rejects_new_rating(inputs):
    scan, policy, _ = inputs
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        image.assess_security(scan, policy)


@pytest.mark.parametrize("field,value", [
    ("Severity", "HIGH"), ("Severity", "UNKNOWN"), ("Severity", "CRITICAL"),
    ("VulnerabilityID", "CVE-new"), ("PkgName", "new-package"),
    ("InstalledVersion", "3.0.22"), ("Status", "fixed"), ("FixedVersion", "3.0.22"),
])
def test_refresh_rejects_changed_or_fixable_findings(inputs, field, value):
    scan, policy, reassessment = inputs
    scan["vulnerabilities"][0][field] = value
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        image.assess_security(scan, policy, os_reassessment=reassessment)


@pytest.mark.parametrize("field", [
    "sources", "evidence", "base_policy_canonical_sha256", "previous_scanner_severity",
    "scanner_severity", "packages", "production_security_approval", "disposition", "basis",
])
def test_entire_reviewed_assessment_is_bound(inputs, field):
    scan, policy, reassessment = inputs
    reassessment[field] = "changed"
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        image.assess_security(scan, policy, os_reassessment=reassessment)


@pytest.mark.parametrize("changed", ["policy", "scanner"])
def test_refresh_rejects_changed_base_inputs(inputs, changed):
    scan, policy, reassessment = inputs
    if changed == "policy":
        policy["unresolved_os_findings"].pop()
    else:
        scan["scanner_image"] = "different-scanner"
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        image.assess_security(scan, policy, os_reassessment=reassessment)
