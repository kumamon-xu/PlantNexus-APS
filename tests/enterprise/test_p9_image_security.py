"""P9-07 explicitly bounded image correction; old assessments remain immutable."""
import json

import pytest

from scripts import enterprise_image_build as image
from tests.enterprise.test_nscd_assessment import assessment as base_assessment, assess

assessment = base_assessment


@pytest.fixture
def risk_inputs():
    policy = json.loads((image.ROOT / 'infra/enterprise/image-security-policy.v1.json').read_text())
    risk = json.loads((image.ROOT / 'infra/enterprise/glibc-risk-assessment.v1.json').read_text())
    scan = {'scanner_image': risk['scanner_image'], 'vulnerabilities': [
        {'class': 'os-pkgs', 'VulnerabilityID': 'CVE-2026-8674', 'PkgName': name,
         'InstalledVersion': '2.36-9+deb12u14', 'Severity': 'MEDIUM', 'Status': 'fix_deferred'}
        for name in ['libc-bin', 'libc6']]}
    return scan, policy, risk


def test_explicit_risk_remains_unresolved_and_not_production(risk_inputs):
    scan, policy, risk = risk_inputs
    with pytest.raises(ValueError, match='NEW_OR_FIXABLE'):
        image.assess_security(scan, policy)
    result = image.assess_security(scan, policy, glibc_risk=risk)
    assert result['production_security_approval'] is False
    assert result['os_component_vex'] == []
    assert result['upstream_os_raw_count'] == 2
    assert result['upstream_os_unique_count'] == 1
    assert len(result['explicitly_accepted_unresolved_findings']) == 2
    assert all(v['disposition'] == 'UNRESOLVED_INTERNAL_TEST_SIMULATION_ONLY'
               for v in result['explicitly_accepted_unresolved_findings'])


@pytest.mark.parametrize('field,value', [
    ('VulnerabilityID', 'CVE-other'), ('PkgName', 'nscd'), ('InstalledVersion', 'other'),
    ('Severity', 'HIGH'), ('Status', 'affected'), ('FixedVersion', 'new-fix'), ('class', 'lang-pkgs'),
])
def test_risk_does_not_authorize_changed_or_fixable_finding(risk_inputs, field, value):
    scan, policy, risk = risk_inputs
    scan['vulnerabilities'][0][field] = value
    with pytest.raises(ValueError, match='NEW_OR_FIXABLE|UNASSESSED_RUNTIME'):
        image.assess_security(scan, policy, glibc_risk=risk)


@pytest.mark.parametrize('field', [
    'sources', 'evidence', 'user_authorization', 'scope', 'basis', 'production_security_approval',
    'disposition', 'base_policy_canonical_sha256',
])
def test_whole_risk_record_is_bound(risk_inputs, field):
    scan, policy, risk = risk_inputs
    risk[field] = 'changed'
    with pytest.raises(ValueError, match='NEW_OR_FIXABLE'):
        image.assess_security(scan, policy, glibc_risk=risk)


@pytest.mark.parametrize('changed', ['scanner', 'policy'])
def test_risk_requires_original_policy_and_scanner(risk_inputs, changed):
    scan, policy, risk = risk_inputs
    if changed == 'scanner':
        scan['scanner_image'] = 'other'
    else:
        policy['unresolved_os_findings'].pop()
    with pytest.raises(ValueError, match='NEW_OR_FIXABLE'):
        image.assess_security(scan, policy, glibc_risk=risk)


@pytest.mark.parametrize('package', ['libc-bin', 'libc6'])
def test_nscd_deferred_refresh_requires_fresh_component_proof(assessment, package):
    finding, evidence, old = assessment
    finding.update(Severity='MEDIUM', Status='fix_deferred', PkgName=package)
    with pytest.raises(ValueError, match='NEW_OR_FIXABLE'):
        assess(finding, evidence, old)
    advisory = json.loads((image.ROOT / 'infra/enterprise/nscd-advisory.v3.json').read_text())
    result = assess(finding, evidence, advisory)
    assert result['os_component_vex'][0]['status'] == 'NOT_AFFECTED'
    evidence['nscd_paths'] = ['/usr/sbin/nscd']
    with pytest.raises(ValueError, match='NEW_OR_FIXABLE'):
        assess(finding, evidence, advisory)


@pytest.mark.parametrize('mutation', ['fix', 'status', 'provenance', 'image', 'missing'])
def test_nscd_refresh_cannot_authorize_invalid_proof(assessment, mutation):
    finding, evidence, _ = assessment
    finding.update(Severity='MEDIUM', Status='fix_deferred')
    advisory = json.loads((image.ROOT / 'infra/enterprise/nscd-advisory.v3.json').read_text())
    if mutation == 'fix':
        finding['FixedVersion'] = 'new-fix'
    elif mutation == 'status':
        finding['Status'] = 'affected'
    elif mutation == 'provenance':
        advisory['retrieved_vendor_document_sha256'] = 'changed'
    elif mutation == 'image':
        evidence['image_id'] = 'sha256:' + '0' * 64
    else:
        evidence['filesystem_scan_complete'] = False
    with pytest.raises(ValueError, match='NEW_OR_FIXABLE'):
        assess(finding, evidence, advisory)


def test_patch_pin_and_frozen_runtime_identity():
    old = json.loads((image.ROOT / 'infra/enterprise/image-inputs.v1.json').read_text())
    current = image.load_inputs()
    assert current['os_patch_packages']['liblzma5'] == '5.4.1-1+deb12u2'
    assert 'liblzma5=5.4.1-1+deb12u2' in (image.ROOT / 'infra/enterprise/Dockerfile').read_text()
    for field in old.keys() - {'schema_version', 'os_patch_packages'}:
        assert current[field] == old[field]
    assert {k: v for k, v in current['os_patch_packages'].items() if k != 'liblzma5'} == old['os_patch_packages']
