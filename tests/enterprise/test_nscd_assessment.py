"""Exact component assessment never becomes a generic OS finding exception."""

from copy import deepcopy
import json

import pytest

from scripts import enterprise_image_build as image

IMAGE = "sha256:" + "1" * 64


@pytest.fixture
def assessment():
    advisory = json.loads(
        (image.ROOT / "infra/enterprise/nscd-advisory.v1.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = {
        "schema_version": "enterprise-nscd-absence.v1",
        "status": "PASS",
        "platform": "linux/amd64",
        "filesystem_scan_complete": True,
        "excluded_virtual_filesystems": ["/proc", "/sys", "/dev"],
        "image_id": IMAGE,
        "inspection_sha256": image.sha256(image.NSCD_INSPECTION.encode()),
        "nscd_package": None,
        "nscd_command": None,
        "nscd_paths": [],
        "dpkg_status_sha256": "2" * 64,
        "glibc_packages": {
            name: {"version": "2.36-9+deb12u14", "status": "install ok installed"}
            for name in ("libc-bin", "libc6")
        },
    }
    finding = {
        "class": "os-pkgs",
        "VulnerabilityID": "CVE-2026-89092",
        "PkgName": "libc6",
        "InstalledVersion": "2.36-9+deb12u14",
        "Severity": "UNKNOWN",
        "Status": "affected",
    }
    return finding, evidence, advisory


def assess(finding, evidence, advisory):
    return image.assess_security(
        {"vulnerabilities": [finding]},
        {"unresolved_os_findings": [], "runtime_vex_assessments": []},
        nscd_evidence=evidence,
        image_id=IMAGE,
        os_advisory=advisory,
    )


@pytest.mark.parametrize("package", ["libc6", "libc-bin"])
def test_absent_component_record_is_explicit_and_not_security_approval(
    assessment, package
):
    finding, evidence, advisory = assessment
    finding["PkgName"] = package
    result = assess(finding, evidence, advisory)
    assert result["os_component_vex"] == [
        {
            "advisory_id": "CVE-2026-89092",
            "package": package,
            "status": "NOT_AFFECTED",
            "justification": "component_not_present",
        }
    ]
    assert (
        result["upstream_os_raw_count"] == 0
        and result["production_security_approval"] is False
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("VulnerabilityID", "CVE-new"),
        ("PkgName", "nscd"),
        ("InstalledVersion", "2.36-other"),
        ("Severity", "HIGH"),
        ("Status", "fixed"),
        ("FixedVersion", "next-version"),
    ],
)
def test_changed_or_fixable_finding_still_refused(assessment, field, value):
    finding, evidence, advisory = assessment
    finding[field] = value
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)


@pytest.mark.parametrize(
    "field,value",
    [
        ("nscd_package", {"version": "present"}),
        ("nscd_command", "/usr/sbin/nscd"),
        ("nscd_paths", ["/tmp/nscd"]),
        ("filesystem_scan_complete", False),
        ("status", "FAIL"),
        ("image_id", "sha256:" + "3" * 64),
        ("inspection_sha256", "4" * 64),
        ("platform", "linux/arm64"),
        ("excluded_virtual_filesystems", ["/proc", "/sys", "/dev", "/usr"]),
        ("glibc_packages", {}),
        ("dpkg_status_sha256", "bad"),
    ],
)
def test_positive_presence_or_incomplete_wrong_image_proof_refused(
    assessment, field, value
):
    finding, evidence, advisory = assessment
    evidence[field] = value
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)


@pytest.mark.parametrize(
    "field",
    ["nscd_package", "nscd_command", "nscd_paths", "image_id", "dpkg_status_sha256"],
)
def test_missing_absence_fields_do_not_default_to_absent(assessment, field):
    finding, evidence, advisory = assessment
    del evidence[field]
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)


def test_no_evidence_and_changed_assessment_refused(assessment):
    finding, evidence, advisory = assessment
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, None, advisory)
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, None)
    advisory["justification"] = "risk_accepted"
    with pytest.raises(ValueError, match="NEW_OR_FIXABLE_OS_FINDING"):
        assess(finding, evidence, advisory)


def test_os_component_evidence_cannot_authorize_python_package(assessment):
    finding, evidence, advisory = assessment
    finding["class"] = "lang-pkgs"
    with pytest.raises(ValueError, match="UNASSESSED_RUNTIME_FINDING"):
        assess(finding, evidence, advisory)


def test_old_unresolved_os_findings_remain_unresolved(assessment):
    finding, evidence, advisory = assessment
    previous = deepcopy(finding)
    previous["VulnerabilityID"] = "CVE-unresolved"
    policy = {
        "unresolved_os_findings": [
            {
                "id": "CVE-unresolved",
                "package": "libc6",
                "version": previous["InstalledVersion"],
                "severity": "UNKNOWN",
                "vendor_status": "affected",
            }
        ],
        "runtime_vex_assessments": [],
    }
    result = image.assess_security(
        {"vulnerabilities": [previous, finding]},
        policy,
        nscd_evidence=evidence,
        image_id=IMAGE,
        os_advisory=advisory,
    )
    assert result["upstream_os_raw_count"] == 1
    assert (
        result["upstream_os_disposition"] == "UNRESOLVED_INTERNAL_TEST_SIMULATION_ONLY"
    )
    assert len(result["os_component_vex"]) == 1


def test_probe_is_bound_to_exact_image_and_read_only_inspection(
    assessment, monkeypatch
):
    _, evidence, _ = assessment
    observed = []

    def run(args, **kwargs):
        observed.append(args)
        return json.dumps(evidence).encode()

    monkeypatch.setattr(image, "run", run)
    result = image.probe_nscd_absence(IMAGE)
    assert result["image_id"] == IMAGE
    assert observed[0][-4:] == [IMAGE, "python", "-c", image.NSCD_INSPECTION]
    for option in (
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--cap-add=DAC_READ_SEARCH",
        "--security-opt=no-new-privileges",
    ):
        assert option in observed[0]
    assert "--privileged" not in observed[0] and "-v" not in observed[0]
