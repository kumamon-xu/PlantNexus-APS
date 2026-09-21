"""Exact Pod::Text absence proof cannot authorize unrelated or fixable findings."""

from copy import deepcopy
import json

import pytest

from scripts import enterprise_image_build as image


IMAGE = "sha256:" + "1" * 64


@pytest.fixture
def inputs():
    policy = json.loads((image.ROOT / "infra/enterprise/image-security-policy.v1.json").read_bytes())
    advisory = json.loads((image.ROOT / "infra/enterprise/pod-text-advisory.v1.json").read_bytes())
    finding = {"class": "os-pkgs", "VulnerabilityID": "CVE-2026-82560", "PkgName": "perl-base",
               "InstalledVersion": "5.36.0-7+deb12u3", "Severity": "UNKNOWN", "Status": "affected"}
    evidence = {"schema_version": "enterprise-pod-text-absence.v1", "status": "PASS",
                "platform": "linux/amd64", "filesystem_scan_complete": True,
                "excluded_virtual_filesystems": ["/proc", "/sys", "/dev"],
                "image_id": IMAGE, "inspection_sha256": image.sha256(image.POD_TEXT_INSPECTION.encode()),
                "dpkg_status_sha256": "a" * 64,
                "perl_base": {"version": "5.36.0-7+deb12u3", "status": "install ok installed"},
                "pod_text_paths": [], "perl_require_returncode": 2,
                "perl_require_module_missing": True, "perl_environment_overrides": []}
    return {"scanner_image": advisory["scanner_image"], "vulnerabilities": [finding]}, policy, advisory, evidence


def assess(values):
    scan, policy, advisory, evidence = values
    return image.assess_security(scan, policy, image_id=IMAGE,
                                 pod_text_advisory=advisory, pod_text_evidence=evidence)


def test_exact_absence_is_explicit_and_not_production_approval(inputs):
    result = assess(inputs)
    assert result["os_component_vex"] == [{"advisory_id": "CVE-2026-82560", "package": "perl-base",
                                           "status": "NOT_AFFECTED", "justification": "component_not_present"}]
    assert result["production_security_approval"] is False
    assert result["explicitly_accepted_unresolved_findings"] == []


@pytest.mark.parametrize("field,value", [
    ("VulnerabilityID", "OTHER"), ("PkgName", "perl"), ("InstalledVersion", "other"),
    ("Severity", "LOW"), ("Status", "fix_deferred"), ("FixedVersion", "fixed"),
    ("class", "lang-pkgs"),
])
def test_changed_or_fixable_finding_rejects(inputs, field, value):
    inputs[0]["vulnerabilities"][0][field] = value
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE|UNASSESSED_RUNTIME"):
        assess(inputs)


@pytest.mark.parametrize("field,value", [
    ("image_id", "sha256:" + "2" * 64), ("inspection_sha256", "changed"),
    ("pod_text_paths", ["/usr/share/perl/Pod/Text.pm"]), ("filesystem_scan_complete", False),
    ("filesystem_scan_complete", 1), ("perl_require_returncode", 0),
    ("perl_require_module_missing", False), ("perl_environment_overrides", ["PERL5LIB"]),
    ("perl_base", {"version": "changed", "status": "install ok installed"}),
    ("dpkg_status_sha256", "invalid"), ("excluded_virtual_filesystems", ["/usr"]),
    ("platform", "linux/arm64"),
])
def test_missing_or_changed_component_proof_rejects(inputs, field, value):
    inputs[3][field] = value
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE"):
        assess(inputs)
    del inputs[3][field]
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE"):
        assess(inputs)


@pytest.mark.parametrize("mutation", ["source", "scanner", "policy", "missing"])
def test_source_and_policy_cannot_be_substituted(inputs, mutation):
    scan, policy, advisory, evidence = deepcopy(inputs)
    if mutation == "source":
        advisory["source"]["sha256"] = "changed"
    elif mutation == "scanner":
        scan["scanner_image"] = "different"
    elif mutation == "policy":
        policy["unresolved_os_findings"].pop()
    else:
        evidence = None
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE"):
        assess((scan, policy, advisory, evidence))
