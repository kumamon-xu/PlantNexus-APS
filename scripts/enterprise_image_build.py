"""Build an internal Runtime image exclusively from a verified release archive.

No repository application source, host environment, or deployment configuration
enters the generated Docker context. The source release remains immutable.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "infra/enterprise/image-inputs.v1.json"
SHA_RE = re.compile(r"[0-9a-f]{40}")
CANARY = b"PNAPS-IMAGE-CANARY-NOT-A-REAL-SECRET"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 1200) -> bytes:
    completed = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=timeout, check=False)
    if completed.returncode:
        # No caller-supplied config/secret values or raw exception text in reports.
        raise RuntimeError(f"COMMAND_FAILED:{args[0]}:{completed.returncode}")
    return completed.stdout


def load_inputs(path: Path = INPUTS) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value["platform"] != "linux/amd64" or not SHA_RE.fullmatch(value["source_sha"]):
        raise ValueError("INVALID_SOURCE_IDENTITY")
    for key in ("base_image", "scanner_image"):
        if not re.fullmatch(r"[a-z0-9./_-]+:[a-z0-9._-]+@sha256:[0-9a-f]{64}", value[key]):
            raise ValueError("UNPINNED_IMAGE")
    return value


def read_release(path: Path, inputs: dict[str, Any]) -> dict[str, bytes]:
    raw = path.read_bytes()
    if sha256(raw) != inputs["archive_sha256"]:
        raise ValueError("ARCHIVE_DIGEST_MISMATCH")
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        total = 0
        for member in archive:
            name = PurePosixPath(member.name)
            if (not member.isfile() or name.is_absolute() or ".." in name.parts
                    or "\\" in member.name or len(name.parts) < 2
                    or name.parts[0] != "plantnexus-aps-runtime-0.1.0-linux-amd64"):
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
            relative = "/".join(name.parts[1:])
            total += member.size
            if relative in files or member.size > 32 * 1024**2 or total > 128 * 1024**2:
                raise ValueError("DUPLICATE_OR_OVERSIZED_ARCHIVE")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("MISSING_ARCHIVE_MEMBER")
            files[relative] = stream.read()
    manifest = json.loads(files["metadata/release-manifest.json"])
    basis = {k: v for k, v in manifest.items() if k != "release_fingerprint"}
    fingerprint = "sha256:" + sha256(json.dumps(
        basis, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    if (manifest["code_commit"] != inputs["source_sha"]
            or fingerprint != inputs["release_fingerprint"]):
        raise ValueError("MANIFEST_IDENTITY_MISMATCH")
    expected = {"metadata/release-manifest.json", "metadata/checksums.sha256"}
    for member in manifest["payload_files"]:
        expected.add(member["path"])
        data = files[member["path"]]
        if len(data) != member["bytes"] or "sha256:" + sha256(data) != member["sha256"]:
            raise ValueError("PAYLOAD_DIGEST_MISMATCH")
    if expected != files.keys():
        raise ValueError("UNEXPECTED_ARCHIVE_MEMBER")
    checksums = {}
    for line in files["metadata/checksums.sha256"].decode().splitlines():
        expected_hash, name = line.split("  ", 1)
        if name in checksums or sha256(files[name]) != expected_hash:
            raise ValueError("CHECKSUM_MISMATCH")
        checksums[name] = expected_hash
    if checksums.keys() != files.keys() - {"metadata/checksums.sha256"}:
        raise ValueError("CHECKSUM_COVERAGE_MISMATCH")
    if sha256(files["runtime/requirements/runtime-requirements.lock"]) != inputs["requirements_sha256"]:
        raise ValueError("REQUIREMENTS_MISMATCH")
    wheels = [n for n in files if n.endswith(".whl")]
    if len(wheels) != 1 or sha256(files[wheels[0]]) != inputs["wheel_sha256"]:
        raise ValueError("WHEEL_MISMATCH")
    return files


def fetch_release(inputs: dict[str, Any], destination: Path) -> Path:
    """Fetch the exact retained Provider artifact; expiry is a hard failure."""
    provider = inputs["provider"]
    raw = run(["gh", "api", f"repos/{provider['repository']}/actions/artifacts/"
               f"{provider['artifact_id']}/zip"])
    if sha256(raw) != provider["artifact_sha256"]:
        raise ValueError("PROVIDER_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.namelist().count(provider["archive_entry"]) != 1:
            raise ValueError("PROVIDER_ARCHIVE_ENTRY_AMBIGUOUS")
        payload = z.read(provider["archive_entry"])
    if sha256(payload) != inputs["archive_sha256"]:
        raise ValueError("PROVIDER_RUNTIME_DIGEST_MISMATCH")
    destination.write_bytes(payload)
    return destination


def prepare_context(files: dict[str, bytes], target: Path, source: Path = ROOT) -> list[dict[str, Any]]:
    target.mkdir(parents=True, exist_ok=False)
    selected = {}
    for name, raw in files.items():
        if name.startswith(("runtime/wheels/", "runtime/requirements/")):
            selected[name.removeprefix("runtime/")] = raw
        elif name.startswith(("runtime/schemas/", "runtime/openapi/", "runtime/backend/migrations/")) or name == "runtime/alembic.ini":
            selected[name] = raw
        elif name.startswith("metadata/"):
            selected[name] = raw
    for name in ("Dockerfile", ".dockerignore", "image_probe.py"):
        selected[name] = (source / "infra/enterprise" / name).read_bytes()
    for name, raw in selected.items():
        path = target/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    # Intentional synthetic negative input: the allow-list Docker ignore must exclude it.
    (target/".env").write_bytes(b"PASSWORD=" + CANARY + b"\n")
    return [{"path": n, "sha256": sha256(b), "bytes": len(b)} for n, b in sorted(selected.items())]


def original_context_check(files: dict[str, bytes], output: Path) -> dict[str, Any]:
    context = output/"original-release"
    context.mkdir()
    for name, data in files.items():
        path = context/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    command = ["docker", "build", "--platform", "linux/amd64", "--progress=plain",
               "-f", str(context/"runtime/container/Dockerfile"), str(context/"runtime")]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=600, check=False)
    (output/"original-dockerfile.log").write_bytes(result.stdout)
    log = result.stdout.decode("utf-8", errors="replace")
    if result.returncode == 0 or not any(n in log for n in ("README.md", "infra/release")):
        raise ValueError("ORIGINAL_DOCKERFILE_FAILURE_NOT_PROVEN")
    return {"status": "EXPECTED_REJECTION", "exit_code": result.returncode,
            "reason": "missing release-context COPY sources", "log_sha256": sha256(result.stdout)}


def inspect_image(image: str, inputs: dict[str, Any], commit: str) -> dict[str, Any]:
    data = json.loads(run(["docker", "image", "inspect", image]))[0]
    if (data["Os"] != "linux" or data["Architecture"] != "amd64"
            or data["Config"]["User"] != "10001:10001"):
        raise ValueError("IMAGE_PLATFORM_OR_USER_MISMATCH")
    labels = data["Config"]["Labels"]
    required = {"org.opencontainers.image.revision": commit,
                "org.opencontainers.image.version": inputs["runtime_version"],
                "io.plantnexus.aps.source-runtime-revision": inputs["source_sha"],
                "io.plantnexus.aps.core.version": inputs["core_version"],
                "io.plantnexus.aps.application.version": inputs["application_version"],
                "io.plantnexus.aps.schema.version": inputs["schema_version_set"]}
    if any(labels.get(k) != v for k, v in required.items()) or not labels.get("org.opencontainers.image.created"):
        raise ValueError("IMAGE_LABEL_MISMATCH")
    if CANARY in json.dumps(data).encode():
        raise ValueError("IMAGE_CONFIG_SECRET_LEAK")
    return data


def probe_image(image_id: str) -> dict[str, Any]:
    base = ["docker", "run", "--rm", "--network=none", "--read-only", "--tmpfs", "/tmp",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", image_id]
    installed = json.loads(run([*base, "python", "image_probe.py"]))
    commands = {"api": ["uvicorn", "--help"],
                "worker": ["celery", "-A", "app.jobs.celery_app:celery_app", "worker", "--help"],
                "migration": ["alembic", "-c", "alembic.ini", "heads"],
                "validator": ["python", "-c", "from app.planning.validation.problem_schedule_validator import validate_problem_schedule; assert callable(validate_problem_schedule)"]}
    checks = []
    for role, command in commands.items():
        raw = run([*base, *command])
        if role == "migration" and b"0009_host_authorization_audit (head)" not in raw:
            raise ValueError("MIGRATION_HEAD_MISMATCH")
        checks.append({"role": role, "image_id": image_id, "command": command, "status": "PASS"})
    return {"installed": installed, "commands": checks, "network": "none",
            "validation_scope": "image role imports/CLI entrypoints, not live deployment"}


def scan_image(archive: Path, inputs: dict[str, Any], output: Path) -> dict[str, Any]:
    cache = output/"trivy-cache"
    cache.mkdir(exist_ok=True)
    args = ["docker", "run", "--rm", "--platform", "linux/amd64",
            "-v", f"{output.resolve()}:/work:ro", "-v", f"{cache.resolve()}:/root/.cache/trivy",
            inputs["scanner_image"]]
    raw = run([*args, "image", "--input", f"/work/{archive.name}", "--format", "json",
               "--list-all-pkgs", "--scanners", "vuln,license,secret", "--license-full"], timeout=1800)
    scan_path = output/"image-scan.json"
    scan_path.write_bytes(raw)
    scan = json.loads(raw)
    if not scan.get("Results"):
        raise ValueError("EMPTY_IMAGE_SCAN")
    secrets = [v for r in scan["Results"] for v in r.get("Secrets", [])]
    if secrets:
        raise ValueError("IMAGE_SECRET_SCAN_FAILED")
    sbom = run([*args, "convert", "--format", "cyclonedx", "/work/image-scan.json"])
    parsed = json.loads(sbom)
    if not parsed.get("components"):
        raise ValueError("EMPTY_SBOM")
    (output/"image-sbom.cdx.json").write_bytes(sbom)
    return {"scanner_image": inputs["scanner_image"], "scan_sha256": sha256(raw),
            "sbom_sha256": sha256(sbom), "component_count": len(parsed["components"]),
            "vulnerabilities": [{"target": r["Target"], "class": r.get("Class"), **v}
                                for r in scan["Results"] for v in r.get("Vulnerabilities", [])],
            "licenses": [{"target": r["Target"], **v}
                         for r in scan["Results"] for v in r.get("Licenses", [])],
            "secret_finding_count": len(secrets), "production_ready": False}


NSCD_INSPECTION = r"""
import hashlib, json, os, platform, shutil
from pathlib import Path
status = Path('/var/lib/dpkg/status').read_bytes()
packages = {}
for paragraph in status.decode().split('\n\n'):
    fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line and not line.startswith(' '))
    if 'Package' in fields:
        packages[fields['Package']] = {'version': fields.get('Version'), 'status': fields.get('Status')}
paths = []
def onerror(error):
    raise error
for folder, dirs, files in os.walk('/', topdown=True, followlinks=False, onerror=onerror):
    if folder == '/':
        dirs[:] = [d for d in dirs if d not in ('proc', 'sys', 'dev')]
    paths.extend(os.path.join(folder, name) for name in dirs + files if 'nscd' in name.lower())
assert platform.machine() == 'x86_64'
print(json.dumps({'schema_version': 'enterprise-nscd-absence.v1', 'status': 'PASS',
    'platform': 'linux/amd64', 'filesystem_scan_complete': True,
    'excluded_virtual_filesystems': ['/proc', '/sys', '/dev'],
    'dpkg_status_sha256': hashlib.sha256(status).hexdigest(),
    'nscd_package': packages.get('nscd'), 'nscd_command': shutil.which('nscd'), 'nscd_paths': paths,
    'glibc_packages': {name: packages[name] for name in ('libc-bin', 'libc6')}}))
"""


def probe_nscd_absence(image_id: str) -> dict[str, Any]:
    # Inspection-only root with read/search capability; no network or writable rootfs.
    raw = run(["docker", "run", "--rm", "--platform", "linux/amd64", "--network=none",
               "--read-only", "--user=0:0", "--cap-drop=ALL", "--cap-add=DAC_READ_SEARCH",
               "--security-opt=no-new-privileges", image_id, "python", "-c", NSCD_INSPECTION])
    return {**json.loads(raw), "image_id": image_id,
            "inspection_sha256": sha256(NSCD_INSPECTION.encode())}


def nscd_not_affected(finding: dict[str, Any], evidence: dict[str, Any] | None,
                      image_id: str | None, advisory: dict[str, Any] | None) -> bool:
    if evidence is None or advisory is None or image_id is None:
        return False
    expected = {"schema_version": "enterprise-component-advisory.v1",
                "advisory_id": "CVE-2026-89092", "status": "NOT_AFFECTED",
                "justification": "component_not_present", "component": "nscd",
                "installed_version": "2.36-9+deb12u14", "scanner_severity": "UNKNOWN",
                "vendor_status": "affected", "affected_binary_packages": ["libc-bin", "libc6"],
                "production_security_approval": False}
    if any(advisory.get(k) != value for k, value in expected.items()):
        return False
    if (finding.get("class") != "os-pkgs" or finding.get("VulnerabilityID") != advisory["advisory_id"]
            or finding.get("PkgName") not in advisory["affected_binary_packages"]
            or finding.get("InstalledVersion") != advisory["installed_version"]
            or finding.get("Severity") != advisory["scanner_severity"]
            or finding.get("Status") != advisory["vendor_status"] or finding.get("FixedVersion")):
        return False
    required = {"schema_version": "enterprise-nscd-absence.v1", "status": "PASS",
                "platform": "linux/amd64", "filesystem_scan_complete": True,
                "excluded_virtual_filesystems": ["/proc", "/sys", "/dev"],
                "image_id": image_id, "inspection_sha256": sha256(NSCD_INSPECTION.encode()),
                "nscd_package": None, "nscd_command": None, "nscd_paths": [],
                "glibc_packages": {name: {"version": "2.36-9+deb12u14", "status": "install ok installed"}
                                   for name in ("libc-bin", "libc6")}}
    return (bool(re.fullmatch(r"sha256:[0-9a-f]{64}", image_id))
            and bool(re.fullmatch(r"[0-9a-f]{64}", evidence.get("dpkg_status_sha256", "")))
            and all(k in evidence and evidence[k] == value for k, value in required.items()))


def assess_security(scan: dict[str, Any], policy: dict[str, Any], *,
                    nscd_evidence: dict[str, Any] | None = None, image_id: str | None = None,
                    os_advisory: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retain unresolved OS risk; never translate a scan into security approval."""
    known = {(v["id"], v["package"], v["version"], v["severity"], v["vendor_status"])
             for v in policy["unresolved_os_findings"]}
    os_findings = []
    os_vex_findings = []
    runtime_findings = []
    for finding in scan["vulnerabilities"]:
        if finding["class"] == "os-pkgs":
            identity = (finding["VulnerabilityID"], finding["PkgName"], finding["InstalledVersion"],
                        finding["Severity"], finding["Status"])
            if nscd_not_affected(finding, nscd_evidence, image_id, os_advisory):
                os_vex_findings.append({"advisory_id": finding["VulnerabilityID"],
                                        "package": finding["PkgName"], "status": "NOT_AFFECTED",
                                        "justification": "component_not_present"})
                continue
            if finding.get("FixedVersion") or identity not in known:
                raise ValueError("NEW_OR_FIXABLE_OS_FINDING")
            os_findings.append(finding["VulnerabilityID"])
        else:
            matches = [a for a in policy["runtime_vex_assessments"]
                       if finding["VulnerabilityID"] in [a["advisory_id"], *a["aliases"]]]
            if (finding["PkgName"] != "starlette" or finding["InstalledVersion"] != "0.47.3"
                    or len(matches) != 1 or matches[0]["status"] != "NOT_AFFECTED"):
                raise ValueError("UNASSESSED_RUNTIME_FINDING")
            runtime_findings.append(matches[0]["advisory_id"])
    return {"assessment_complete": True, "production_security_approval": False,
            "upstream_os_disposition": "UNRESOLVED_INTERNAL_TEST_SIMULATION_ONLY",
            "upstream_os_raw_count": len(os_findings), "upstream_os_unique_count": len(set(os_findings)),
            "runtime_vex_unique_count": len(set(runtime_findings)),
            "os_component_vex": os_vex_findings,
            "runtime_vex_reuse_basis": "exact original wheel/source hash and Linux target unchanged",
            "unrecognized_or_fixable_finding_count": 0}


def verify_installed_licenses(probes: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    license_report = json.loads(files["metadata/license-report.json"])
    if license_report["status"] != "PASS" or license_report["issues"]:
        raise ValueError("SOURCE_LICENSE_REPORT_FAILED")
    expected = {(v["name"], v["version"]): v for v in license_report["components"]}
    installed = probes["installed"]["packages"]
    for package in installed:
        key = (package["name"].lower().replace("_", "-"), package["version"])
        if key not in expected or expected[key]["status"] != "PASS" or not expected[key]["license_expression"]:
            raise ValueError("UNREVIEWED_INSTALLED_PACKAGE")
    return {"status": "PASS", "installed_component_count": len(installed),
            "source_policy_component_count": len(expected),
            "basis": "exact installed name/version against immutable Runtime license report",
            "os_licenses": "full scan inventory and upstream copyright notices retained; no legal approval claim"}


def verify_no_canary(archive: Path) -> None:
    """Check every saved layer, including gzip OCI blobs, not only final files."""
    with tarfile.open(archive) as saved:
        for member in saved:
            if not member.isfile():
                continue
            stream = saved.extractfile(member)
            if stream is None:
                raise ValueError("UNREADABLE_IMAGE_LAYER")
            first = stream.read(2)
            stream.seek(0)
            content = gzip.GzipFile(fileobj=stream) if first == b"\x1f\x8b" else stream
            previous = b""
            while block := content.read(1024 * 1024):
                if CANARY in previous + block:
                    raise ValueError("IMAGE_LAYER_CANARY_LEAK")
                previous = block[-len(CANARY):]


def build(args: argparse.Namespace) -> dict[str, Any]:
    inputs = load_inputs()
    commit = run(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    if not SHA_RE.fullmatch(commit):
        raise ValueError("INVALID_PACKAGING_SHA")
    dirty = bool(run(["git", "status", "--porcelain"], cwd=ROOT))
    if dirty and not args.candidate:
        raise ValueError("DIRTY_RELEASE_INPUT")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/"build").resolve()):
        raise ValueError("OUTPUT_OUTSIDE_BUILD")
    output.mkdir(parents=True, exist_ok=False)
    archive = args.archive or fetch_release(inputs, output/"source-runtime.tar.gz")
    files = read_release(archive, inputs)
    original = original_context_check(files, output)
    inventory = prepare_context(files, output/"context")
    write_json(output/"context-inventory.json", inventory)
    timestamp = run(["git", "show", "-s", "--format=%ct", commit], cwd=ROOT).decode().strip()
    created = datetime.fromtimestamp(int(timestamp), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tag = f"{inputs['image_name']}:{'candidate-' if args.candidate else ''}{inputs['runtime_version']}-{commit}"
    command = ["docker", "build", "--platform", inputs["platform"], "--progress=plain",
               "--build-arg", f"APS_PACKAGING_SHA={commit}", "--build-arg", f"APS_CREATED={created}",
               "--build-arg", f"SOURCE_DATE_EPOCH={timestamp}", "-t", tag, str(output/"context")]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=1800, check=False)
    (output/"build.log").write_bytes(result.stdout)
    if result.returncode:
        raise ValueError("ENTERPRISE_IMAGE_BUILD_FAILED")
    identity = inspect_image(tag, inputs, commit)
    probes = probe_image(identity["Id"])
    licenses = verify_installed_licenses(probes, files)
    image_tar = output/f"plantnexus-aps-runtime-{inputs['runtime_version']}-linux-amd64.tar"
    run(["docker", "save", "-o", str(image_tar), tag])
    verify_no_canary(image_tar)
    image_hash = sha256(image_tar.read_bytes())
    image_tar.with_suffix(".tar.sha256").write_text(f"{image_hash}  {image_tar.name}\n", encoding="ascii")
    scan = scan_image(image_tar, inputs, output)
    policy = json.loads((ROOT/"infra/enterprise/image-security-policy.v1.json").read_text())
    if policy["runtime_wheel_sha256"] != inputs["wheel_sha256"] or policy["runtime_source_sha"] != inputs["source_sha"]:
        raise ValueError("VEX_SOURCE_IDENTITY_MISMATCH")
    nscd_evidence = probe_nscd_absence(identity["Id"])
    os_advisory = json.loads((ROOT/"infra/enterprise/nscd-advisory.v1.json").read_text(encoding="utf-8"))
    assessment = assess_security(scan, policy, nscd_evidence=nscd_evidence,
                                 image_id=identity["Id"], os_advisory=os_advisory)
    return {"schema_version": "enterprise-runtime-image-report.v1", "task_id": "TASK-P8-23",
            "code_commit": commit, "source_runtime_sha": inputs["source_sha"],
            "source_archive_sha256": inputs["archive_sha256"], "candidate": args.candidate,
            "dirty": dirty, "status": "PASS", "issues": [], "tag": tag,
            "image_id": identity["Id"], "repo_digests": identity.get("RepoDigests", []),
            "labels": identity["Config"]["Labels"], "platform": inputs["platform"],
            "base_image": inputs["base_image"], "original_dockerfile": original,
            "context_inventory": inventory, "probes": probes,
            "image_archive": str(image_tar.relative_to(ROOT)), "image_archive_sha256": image_hash,
            "security": scan, "security_assessment": assessment, "runtime_licenses": licenses,
            "nscd_component_evidence": nscd_evidence, "os_component_advisory": os_advisory,
            "production_ready": False,
            "runtime_deployment_tested": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    try:
        report = build(args)
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.SubprocessError) as error:
        report = {"status": "FAIL", "task_id": "TASK-P8-23", "code_commit": os.environ.get("GITHUB_SHA"),
                  "issues": [str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__]}
    write_json(args.report, report)
    print(json.dumps({"status": report["status"], "report": str(args.report), "issues": report["issues"]}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
