"""Enriched CVE metadata needs a new bounded assessment and fresh component proof."""

import json

import pytest

from scripts import enterprise_image_build as image
from tests.enterprise.test_nscd_assessment import assessment as base_assessment, assess

assessment = base_assessment


@pytest.fixture
def refreshed(assessment):
    finding, evidence, _ = assessment
    finding["Severity"] = "MEDIUM"
    advisory = json.loads(
        (image.ROOT / "infra/enterprise/nscd-advisory.v2.json").read_text(
            encoding="utf-8"
        )
    )
    return finding, evidence, advisory


@pytest.mark.parametrize("package", ["libc6", "libc-bin"])
def test_medium_refresh_requires_explicit_new_assessment(refreshed, package):
    finding, evidence, advisory = refreshed
    finding["PkgName"] = package
    result = assess(finding, evidence, advisory)
    assert result["os_component_vex"][0]["status"] == "NOT_AFFECTED"
    assert result["production_security_approval"] is False


def test_old_unknown_assessment_cannot_authorize_medium(assessment):
    finding, evidence, advisory = assessment
    finding["Severity"] = "MEDIUM"
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)


@pytest.mark.parametrize("severity", ["UNKNOWN", "LOW", "HIGH", "CRITICAL"])
def test_refresh_does_not_accept_other_severities(refreshed, severity):
    finding, evidence, advisory = refreshed
    finding["Severity"] = severity
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)


@pytest.mark.parametrize(
    "field,value",
    [
        ("VulnerabilityID", "CVE-new"),
        ("PkgName", "nscd"),
        ("InstalledVersion", "new-version"),
        ("Status", "fixed"),
        ("FixedVersion", "available-fix"),
    ],
)
def test_refresh_still_blocks_new_changed_and_fixable_findings(refreshed, field, value):
    finding, evidence, advisory = refreshed
    finding[field] = value
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)


@pytest.mark.parametrize(
    "field,value",
    [
        ("nscd_package", {}),
        ("nscd_command", "/sbin/nscd"),
        ("nscd_paths", ["/tmp/nscd"]),
        ("image_id", "sha256:" + "0" * 64),
        ("filesystem_scan_complete", False),
    ],
)
def test_refresh_requires_complete_fresh_exact_image_absence(refreshed, field, value):
    finding, evidence, advisory = refreshed
    evidence[field] = value
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)


@pytest.mark.parametrize(
    "field",
    [
        "supersedes_advisory_sha256",
        "retrieved_vendor_document_sha256",
        "assessment_date",
        "previous_scanner_severity",
        "justification",
        "component",
    ],
)
def test_refresh_provenance_and_basis_are_bound(refreshed, field):
    finding, evidence, advisory = refreshed
    advisory[field] = "changed"
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)
