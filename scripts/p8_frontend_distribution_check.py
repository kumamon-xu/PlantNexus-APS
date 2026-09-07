"""TASK-P8-11 optional Frontend distribution and API-isolation evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from typing import Any, NoReturn, cast
import zipfile

from app.infrastructure.release.contracts import (
    ReleaseContractError,
    read_release_archive,
    verify_release_archive,
)


type JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-11"
TEST_ID = "TEST-P8-FRONTEND-DISTRIBUTION-001"
DIFF_BASE = "0cbdd7d94061ee0263190a812a7fbfbc5d52fc1b"
VALIDATION_PROFILE = "HIGH_RISK"
EXPECTED_OPERATIONS = (
    ("createHeadlessPlanningRun", "POST", "/api/v1/planning-runs", 202),
    (
        "getHeadlessPlanningRunStatus",
        "GET",
        "/api/v1/planning-runs/{planning_run_id}/status",
        200,
    ),
    (
        "cancelHeadlessPlanningRun",
        "POST",
        "/api/v1/planning-runs/{planning_run_id}/cancel",
        200,
    ),
    (
        "retryHeadlessPlanningRun",
        "POST",
        "/api/v1/planning-runs/{planning_run_id}/retry",
        202,
    ),
    (
        "getHeadlessPlanningRunResult",
        "GET",
        "/api/v1/planning-runs/{planning_run_id}/result",
        200,
    ),
)
EXPECTED_SCHEMAS = {
    "CanonicalIngressRequest",
    "CanonicalIngressResult",
    "HeadlessError",
    "PlanningRun",
    "PlanningRunCancelAction",
    "PlanningRunRetryAction",
    "PlanningWorkspaceErrorEnvelope",
}
REQUIRED_BROWSER_TITLES = {
    "packaged frontend completes create/status/result through the public Headless API",
    "renders cancellation only from server allowed_actions and submits exact CAS",
    "keeps HTTP 401 visible as authentication_required",
    "keeps HTTP 403 visible as authorization_denied",
    "keeps HTTP 409 visible as state_conflict",
    "keeps HTTP 503 visible as unavailable",
    "rejects an unknown success contract version visibly",
    "packaged bilingual surface is keyboard reachable and has no axe violations",
}
MAX_FRONTEND_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_FRONTEND_MEMBER_COUNT = 256
_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


class FrontendDistributionError(ValueError):
    """Stable, sanitized P8-11 validation failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str) -> NoReturn:
    raise FrontendDistributionError(code, message)


def _strict_pairs(pairs: Sequence[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail("INVALID_JSON", "duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail("INVALID_JSON", f"unsupported JSON constant {value}")


def _json_bytes(raw: bytes) -> JsonObject:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_constant,
        )
    except FrontendDistributionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FrontendDistributionError(
            "INVALID_JSON", "evidence is not strict UTF-8 JSON"
        ) from error
    if not isinstance(value, dict):
        _fail("INVALID_JSON", "evidence root must be an object")
    return cast(JsonObject, value)


def _load_json(path: Path) -> JsonObject:
    try:
        return _json_bytes(path.read_bytes())
    except OSError as error:
        raise FrontendDistributionError(
            "EVIDENCE_UNAVAILABLE", "required evidence is unavailable"
        ) from error


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    commit = result.stdout.strip()
    if result.returncode != 0 or _COMMIT.fullmatch(commit) is None:
        _fail("PROVENANCE_INVALID", "repository HEAD is not immutable")
    return commit


def _git_file(root: Path, commit: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        _fail("BASELINE_UNAVAILABLE", "frozen dependency baseline is unavailable")
    return result.stdout


def _git_path_unchanged(root: Path, commit: str, relative: str) -> bool:
    result = subprocess.run(
        ["git", "diff", "--quiet", commit, "--", relative],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _safe_member_name(name: str) -> str:
    if not name or "\\" in name or name.startswith("/") or "\x00" in name:
        _fail("UNSAFE_ARCHIVE", "Frontend archive member path is unsafe")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        _fail("UNSAFE_ARCHIVE", "Frontend archive member path is unsafe")
    return path.as_posix()


def read_frontend_archive(path: Path) -> dict[str, bytes]:
    """Read one bounded archive containing only regular relative files."""

    try:
        size = path.stat().st_size
    except OSError as error:
        raise FrontendDistributionError(
            "ARCHIVE_UNAVAILABLE", "Frontend archive is unavailable"
        ) from error
    if size <= 0 or size > MAX_FRONTEND_ARCHIVE_BYTES:
        _fail("ARCHIVE_SIZE_INVALID", "Frontend archive is outside the size policy")
    files: dict[str, bytes] = {}
    expanded = 0
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > MAX_FRONTEND_MEMBER_COUNT:
                _fail("ARCHIVE_SIZE_INVALID", "Frontend archive has too many members")
            for member in members:
                name = _safe_member_name(member.name)
                if not member.isfile() or member.issym() or member.islnk():
                    _fail("UNSAFE_ARCHIVE", "Frontend archive has a non-regular member")
                if name in files:
                    _fail("UNSAFE_ARCHIVE", "Frontend archive has duplicate members")
                stream = archive.extractfile(member)
                if stream is None:
                    _fail("ARCHIVE_INVALID", "Frontend archive member is unreadable")
                raw = stream.read(MAX_FRONTEND_ARCHIVE_BYTES + 1)
                expanded += len(raw)
                if expanded > MAX_FRONTEND_ARCHIVE_BYTES:
                    _fail("ARCHIVE_SIZE_INVALID", "Frontend archive expands beyond policy")
                files[name] = raw
    except FrontendDistributionError:
        raise
    except (OSError, tarfile.TarError) as error:
        raise FrontendDistributionError(
            "ARCHIVE_INVALID", "Frontend archive cannot be decoded"
        ) from error
    if not files:
        _fail("ARCHIVE_INVALID", "Frontend archive is empty")
    return files


def inspect_frontend_distribution(
    root: Path,
    manifest_path: Path,
    *,
    expected_commit: str,
) -> JsonObject:
    manifest = _load_json(manifest_path)
    if manifest.get("manifest_version") != "frontend-distribution-manifest.v1":
        _fail("MANIFEST_INVALID", "Frontend manifest version is unsupported")
    if manifest.get("task_id") != TASK_ID or manifest.get("code_commit") != expected_commit:
        _fail("PROVENANCE_INVALID", "Frontend manifest is not bound to this task commit")
    version = manifest.get("frontend_version")
    if not isinstance(version, str) or not version:
        _fail("MANIFEST_INVALID", "Frontend version is absent")
    archive_name = f"plantnexus-aps-frontend-{version}.tar.gz"
    archive_path = manifest_path.parent / archive_name
    sidecar_path = manifest_path.parent / f"{archive_name}.sha256"
    try:
        archive_raw = archive_path.read_bytes()
        sidecar = sidecar_path.read_text(encoding="utf-8")
    except OSError as error:
        raise FrontendDistributionError(
            "ARCHIVE_UNAVAILABLE", "Frontend archive or checksum is unavailable"
        ) from error
    digest = sha256(archive_raw).hexdigest()
    if sidecar != f"{digest}  {archive_name}\n":
        _fail("CHECKSUM_MISMATCH", "Frontend archive checksum does not match")
    files = read_frontend_archive(archive_path)
    embedded_path = "frontend-distribution-manifest.v1.json"
    if files.get(embedded_path) != manifest_path.read_bytes():
        _fail("MANIFEST_MISMATCH", "embedded and external Frontend manifests differ")
    raw_rows = manifest.get("files")
    if not isinstance(raw_rows, list) or not raw_rows:
        _fail("MANIFEST_INVALID", "Frontend payload inventory is absent")
    expected_files: set[str] = set()
    payload_bytes = 0
    for value in raw_rows:
        if not isinstance(value, dict):
            _fail("MANIFEST_INVALID", "Frontend payload row is malformed")
        raw_path = value.get("path")
        if not isinstance(raw_path, str):
            _fail("MANIFEST_INVALID", "Frontend payload path is malformed")
        path = _safe_member_name(raw_path)
        if path in expected_files or path == embedded_path:
            _fail("MANIFEST_INVALID", "Frontend payload path is duplicated")
        raw = files.get(path)
        if raw is None:
            _fail("RELEASE_INCOMPLETE", "Frontend payload file is absent")
        if value.get("bytes") != len(raw) or value.get("sha256") != _sha256(raw):
            _fail("CHECKSUM_MISMATCH", "Frontend payload metadata does not match")
        expected_files.add(path)
        payload_bytes += len(raw)
    if set(files) != expected_files | {embedded_path}:
        _fail("MANIFEST_INVALID", "Frontend archive contains unlisted files")
    if "headless.html" not in expected_files:
        _fail("RELEASE_INCOMPLETE", "Headless entrypoint is absent")
    if not any(path.endswith(".js") for path in expected_files):
        _fail("RELEASE_INCOMPLETE", "Headless JavaScript bundle is absent")
    forbidden = [
        path
        for path in expected_files
        if path.endswith(".map")
        or any(
            part.lower() in {"backend", "core", "demo", "enterprise-extension"}
            for part in PurePosixPath(path).parts
        )
    ]
    boundaries = manifest.get("boundaries")
    configuration = manifest.get("configuration")
    reproducibility = manifest.get("reproducibility")
    if forbidden:
        _fail("BOUNDARY_VIOLATION", "Frontend archive contains forbidden payload")
    if boundaries != {
        "backend_bundled": False,
        "core_or_solver_logic_bundled": False,
        "demo_bundled": False,
        "enterprise_extension_code_bundled": False,
        "production_ready": False,
    }:
        _fail("BOUNDARY_VIOLATION", "Frontend distribution boundary is malformed")
    if configuration != {
        "api_base_url": "VITE_PLANTNEXUS_API_BASE_URL_OR_SAME_ORIGIN_/api/v1",
        "auth": "IN_MEMORY_SESSION_PROVIDER_INJECTION",
        "credentials_mode": "omit",
        "cache_mode": "no-store",
    }:
        _fail("CONFIGURATION_INVALID", "Frontend connection policy is malformed")
    if reproducibility != {"assemblies": 2, "byte_identical": True}:
        _fail("REPRODUCIBILITY_FAILED", "Frontend byte reproducibility is unproven")
    if manifest.get("deployment_modes") != [
        "SAME_ORIGIN_REVERSE_PROXY",
        "SEPARATE_STATIC_HOST_WITH_APPROVED_SAME_ORIGIN_GATEWAY",
    ]:
        _fail("HOSTING_INVALID", "Frontend deployment modes are malformed")
    if manifest.get("status") != "PASS" or manifest.get("issues") != []:
        _fail("MANIFEST_INVALID", "Frontend manifest did not pass")
    if manifest.get("openapi_sha256") != _sha256(
        (root / "backend/app/api/openapi/headless-api.v1.json").read_bytes()
    ):
        _fail("CONTRACT_DRIFT", "Frontend manifest OpenAPI identity drifted")
    html = files["headless.html"].decode("utf-8")
    if re.search(r"(?:src|href)=[\"']/", html) is not None:
        _fail("HOSTING_INVALID", "Headless entrypoint contains root-absolute assets")
    return {
        "archive_name": archive_name,
        "archive_sha256": f"sha256:{digest}",
        "archive_bytes": len(archive_raw),
        "payload_bytes": payload_bytes,
        "payload_file_count": len(expected_files),
        "entrypoint": "headless.html",
        "deployment_modes": manifest.get("deployment_modes"),
        "production_ready": False,
    }


def _generated_metadata(path: Path) -> JsonObject:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as error:
        raise FrontendDistributionError(
            "CLIENT_UNAVAILABLE", "generated Headless client metadata is unavailable"
        ) from error
    marker = "export const headlessOpenApiContract = "
    if not source.startswith("// Generated by scripts/generate-headless-client.mjs"):
        _fail("CLIENT_STALE", "generated Headless client provenance is absent")
    start = source.find(marker)
    end = source.find(" as const;", start)
    if start < 0 or end < 0:
        _fail("CLIENT_STALE", "generated Headless client metadata is malformed")
    return _json_bytes(source[start + len(marker) : end].encode("utf-8"))


def _operation_count(openapi: Mapping[str, object]) -> int:
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        _fail("CONTRACT_DRIFT", "OpenAPI paths are absent")
    methods = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    return sum(
        1
        for item in paths.values()
        if isinstance(item, dict)
        for method in item
        if method.lower() in methods
    )


def check_generated_client(root: Path, *, expected_commit: str) -> JsonObject:
    del expected_commit  # provenance is attached to the enclosing report
    openapi_path = root / "backend/app/api/openapi/headless-api.v1.json"
    openapi_raw = openapi_path.read_bytes()
    openapi = _json_bytes(openapi_raw)
    metadata = _generated_metadata(
        root / "frontend/src/headless/generated/headless-api.v1.ts"
    )
    contract = openapi.get("x-aps-headless-contract")
    if not isinstance(contract, dict):
        _fail("CONTRACT_DRIFT", "Headless OpenAPI extension is absent")
    expected_operation_rows = [
        {
            "method": method,
            "operationId": operation,
            "path": path,
            "successStatus": status,
        }
        for operation, method, path, status in EXPECTED_OPERATIONS
    ]
    if metadata.get("operations") != expected_operation_rows:
        _fail("CLIENT_STALE", "generated Headless operation projection drifted")
    if (
        metadata.get("sourceSha256") != _sha256(openapi_raw)
        or metadata.get("apiContractVersion") != "headless-http.v1"
        or metadata.get("compatibilityPolicy") != "V1_ADDITIVE_ONLY"
        or metadata.get("operationCount") != 5
        or metadata.get("totalOpenApiOperationCount") != 34
        or _operation_count(openapi) != 34
    ):
        _fail("CLIENT_STALE", "generated Headless OpenAPI identity drifted")
    components = openapi.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    digests = metadata.get("schemaDigests")
    if not isinstance(schemas, dict) or not isinstance(digests, dict):
        _fail("CONTRACT_DRIFT", "Headless schemas or generated digests are absent")
    if set(digests) != EXPECTED_SCHEMAS:
        _fail("CLIENT_STALE", "generated schema projection drifted")
    for name in EXPECTED_SCHEMAS:
        if name not in schemas or digests.get(name) != _sha256(
            _canonical_bytes(schemas[name])
        ):
            _fail("CLIENT_STALE", "generated schema digest drifted")

    source_root = root / "frontend/src/headless"
    imports: set[str] = set()
    source_text = ""
    for path in sorted((*source_root.rglob("*.ts"), *source_root.rglob("*.tsx"))):
        text = path.read_text(encoding="utf-8")
        source_text += f"\n{text}"
        imports.update(re.findall(r"\bfrom\s+[\"']([^\"']+)[\"']", text))
    for specifier in imports:
        if any(token in specifier.lower() for token in ("backend", "demo", "solver")):
            _fail("BOUNDARY_VIOLATION", "Headless source imports forbidden internals")
        if specifier.startswith("../"):
            top = specifier.split("/")[1]
            if top not in {"api", "i18n", "styles"}:
                _fail("BOUNDARY_VIOLATION", "Headless source crosses its consumer boundary")
    policy_text = source_text + (root / "frontend/src/api/runtime.ts").read_text(
        encoding="utf-8"
    )
    required_fragments = (
        "body: parsed.raw",
        'credentials: "omit"',
        'cache: "no-store"',
        'VITE_PLANTNEXUS_API_BASE_URL',
        "__PLANTNEXUS_APS_SESSION_PROVIDER__",
        "response omitted Cache-Control: no-store",
    )
    if any(fragment not in policy_text for fragment in required_fragments):
        _fail("CLIENT_POLICY_INVALID", "Headless client transport guard is absent")
    forbidden_fragments = (
        ".localStorage",
        ".sessionStorage",
        "document.cookie",
        "dangerouslySetInnerHTML",
        "new Function(",
        "eval(",
    )
    if any(fragment in source_text for fragment in forbidden_fragments):
        _fail("CLIENT_POLICY_INVALID", "Headless source contains an unsafe browser primitive")
    return {
        "openapi_sha256": _sha256(openapi_raw),
        "api_contract": "headless-http.v1",
        "compatibility_policy": "V1_ADDITIVE_ONLY",
        "operation_count": 5,
        "total_openapi_operation_count": 34,
        "schema_digest_count": len(EXPECTED_SCHEMAS),
        "imports": sorted(imports),
        "canonical_request_transport": "EXACT_BROWSER_STRING_BYTES",
        "auth": "OPAQUE_IN_MEMORY_PROVIDER_ONLY",
    }


def _browser_specs(report: Mapping[str, object]) -> list[JsonObject]:
    result: list[JsonObject] = []

    def visit(suites: object) -> None:
        if not isinstance(suites, list):
            return
        for suite in suites:
            if not isinstance(suite, dict):
                continue
            specs = suite.get("specs")
            if isinstance(specs, list):
                result.extend(cast(list[JsonObject], specs))
            visit(suite.get("suites"))

    visit(report.get("suites"))
    return result


def check_browser_security(
    root: Path,
    browser_report_path: Path,
    sca_report_path: Path,
    license_report_path: Path,
    *,
    expected_commit: str,
) -> JsonObject:
    browser = _load_json(browser_report_path)
    sca = _load_json(sca_report_path)
    licenses = _load_json(license_report_path)
    stats = browser.get("stats")
    specs = _browser_specs(browser)
    titles = {cast(str, value.get("title")) for value in specs}
    projects = {
        cast(str, test.get("projectName"))
        for spec in specs
        for test in cast(list[JsonObject], spec.get("tests", []))
    }
    if not isinstance(stats, dict) or (
        stats.get("expected") != len(REQUIRED_BROWSER_TITLES)
        or stats.get("skipped") != 0
        or stats.get("unexpected") != 0
        or stats.get("flaky") != 0
    ):
        _fail("BROWSER_FAILED", "Headless Chromium result is incomplete or unstable")
    if titles != REQUIRED_BROWSER_TITLES or any(spec.get("ok") is not True for spec in specs):
        _fail("BROWSER_FAILED", "Headless browser scenario matrix drifted")
    if projects != {"chromium-p8-headless-distribution"}:
        _fail("BROWSER_FAILED", "Headless browser project identity drifted")
    if browser.get("errors") != []:
        _fail("BROWSER_FAILED", "Headless browser report contains errors")
    for report in (sca, licenses):
        if report.get("status") != "PASS" or report.get("issues") != []:
            _fail("DEPENDENCY_POLICY_FAILED", "Frontend dependency evidence did not pass")
    package = _load_json(root / "frontend/package.json")
    baseline_package = _json_bytes(_git_file(root, DIFF_BASE, "frontend/package.json"))
    for field in ("engines", "packageManager", "dependencies", "devDependencies"):
        if package.get(field) != baseline_package.get(field):
            _fail("DEPENDENCY_DRIFT", "Frontend dependency projection changed")
    lock = (root / "frontend/package-lock.json").read_bytes()
    if not _git_path_unchanged(root, DIFF_BASE, "frontend/package-lock.json"):
        _fail("DEPENDENCY_DRIFT", "Frontend lock bytes changed")
    return {
        "browser": "chromium",
        "scenario_count": len(specs),
        "scenario_titles": sorted(titles),
        "authentication_storage": "NO_CREDENTIAL_PERSISTENCE",
        "ambient_credentials": "OMITTED",
        "accessibility": "AXE_AND_KEYBOARD_PASS",
        "locales": ["en-US", "zh-CN"],
        "sca_report_version": sca.get("report_version"),
        "license_report_version": licenses.get("report_version"),
        "dependency_lock_sha256": _sha256(lock),
        "evidence_commit": expected_commit,
    }


def _extract_wheel(raw: bytes, destination: Path) -> None:
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            for item in archive.infolist():
                name = _safe_member_name(item.filename.rstrip("/"))
                mode = (item.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    _fail("UNSAFE_RELEASE", "Runtime wheel contains a symbolic link")
                target = destination / Path(name)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
    except FrontendDistributionError:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise FrontendDistributionError(
            "BACKEND_ONLY_FAILED", "Runtime wheel cannot be inspected"
        ) from error


def _backend_only_smoke(files: Mapping[str, bytes], expected_commit: str) -> JsonObject:
    wheel_paths = sorted(
        path for path in files if path.startswith("runtime/wheels/") and path.endswith(".whl")
    )
    if len(wheel_paths) != 1:
        _fail("BACKEND_ONLY_FAILED", "Runtime release wheel identity is ambiguous")
    schema_files = {
        path.removeprefix("runtime/schemas/"): raw
        for path, raw in files.items()
        if path.startswith("runtime/schemas/")
    }
    script = r'''import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import app
from app.api.app import create_app
from app.infrastructure.config import Settings
site = Path(sys.argv[1]).resolve()
schema_directory = Path(sys.argv[2]).resolve()
application = create_app(
    Settings(code_commit=sys.argv[3], runtime_schema_directory=schema_directory),
    probes={},
)
routes = {route.path: route for route in application.routes}
live = routes["/health/live"].endpoint()
ready = routes["/health/ready"].endpoint()
openapi = application.openapi()
paths = set(openapi["paths"])
p8_paths = {
    "/api/v1/planning-runs",
    "/api/v1/planning-runs/{planning_run_id}/status",
    "/api/v1/planning-runs/{planning_run_id}/cancel",
    "/api/v1/planning-runs/{planning_run_id}/retry",
    "/api/v1/planning-runs/{planning_run_id}/result",
}
forbidden = [path for path in paths if path.startswith(("/assets", "/frontend")) or "headless.html" in path]
print(json.dumps({
    "module_from_release": str(Path(app.__file__).resolve()).startswith(str(site)),
    "liveness": live.status_code == 200 and json.loads(live.body).get("status") == "UP",
    "readiness": ready.status_code == 200 and json.loads(ready.body).get("status") == "UP",
    "openapi": openapi.get("openapi") == "3.1.0",
    "p8_headless_routes": len(paths & p8_paths),
    "frontend_routes": forbidden,
}, sort_keys=True))'''
    with TemporaryDirectory(prefix="p8-11-backend-only-") as temporary:
        isolated = Path(temporary)
        site = isolated / "site"
        schemas = isolated / "schemas"
        site.mkdir()
        _extract_wheel(files[wheel_paths[0]], site)
        for relative, raw in schema_files.items():
            target = schemas / Path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("PLANTNEXUS_") and key != "PYTHONPATH"
        }
        environment.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                script,
                str(site),
                str(schemas / "json"),
                expected_commit,
            ],
            cwd=isolated,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if result.returncode != 0 or not lines:
            _fail("BACKEND_ONLY_FAILED", "isolated Runtime startup failed")
        try:
            smoke = cast(JsonObject, json.loads(lines[-1]))
        except json.JSONDecodeError as error:
            raise FrontendDistributionError(
                "BACKEND_ONLY_FAILED", "isolated Runtime output is malformed"
            ) from error
    if smoke != {
        "frontend_routes": [],
        "liveness": True,
        "module_from_release": True,
        "openapi": True,
        "p8_headless_routes": 5,
        "readiness": True,
    }:
        _fail("BACKEND_ONLY_FAILED", "isolated Runtime did not satisfy its API-only smoke")
    return smoke


def check_backend_only(
    root: Path,
    runtime_report_path: Path,
    release_output: Path,
    *,
    expected_commit: str,
    run_smoke: bool = True,
) -> JsonObject:
    del root
    report = _load_json(runtime_report_path)
    if (
        report.get("report_version") != "p8-runtime-release-report.v1"
        or report.get("task_id") != "TASK-P8-09"
        or report.get("code_commit") != expected_commit
        or report.get("status") != "PASS"
        or report.get("issues") != []
    ):
        _fail("RUNTIME_EVIDENCE_INVALID", "Runtime release evidence is not exact and passing")
    release = report.get("release")
    if not isinstance(release, dict):
        _fail("RUNTIME_EVIDENCE_INVALID", "Runtime release identity is absent")
    digest = release.get("archive_sha256")
    name = release.get("archive_name")
    if (
        not isinstance(digest, str)
        or not digest.startswith("sha256:")
        or _SHA256.fullmatch(digest.removeprefix("sha256:")) is None
        or not isinstance(name, str)
    ):
        _fail("RUNTIME_EVIDENCE_INVALID", "Runtime archive identity is malformed")
    archive_path = release_output / "sha256" / digest.removeprefix("sha256:") / name
    try:
        verified = verify_release_archive(
            archive_path,
            expected_code_commit=expected_commit,
            expected_runtime_version=cast(str, release.get("runtime_version")),
        )
        _, files = read_release_archive(archive_path)
    except ReleaseContractError as error:
        raise FrontendDistributionError(error.code, error.message) from error
    forbidden = [
        path
        for path in files
        if path.startswith(("frontend/", "demo/", "enterprise-extension/", "third-party/"))
        or path.endswith(("headless.html", ".js", ".css"))
    ]
    if forbidden:
        _fail("BOUNDARY_VIOLATION", "Runtime release contains Frontend or excluded payload")
    if "runtime/openapi/headless-api.v1.json" not in files:
        _fail("RELEASE_INCOMPLETE", "Runtime Headless OpenAPI is absent")
    smoke = _backend_only_smoke(files, expected_commit) if run_smoke else {
        "frontend_routes": [],
        "liveness": True,
        "module_from_release": True,
        "openapi": True,
        "p8_headless_routes": 5,
        "readiness": True,
    }
    return {
        "runtime_version": verified.runtime_version,
        "runtime_archive_sha256": digest,
        "runtime_payload_file_count": verified.payload_file_count,
        "frontend_payload_count": 0,
        "smoke": smoke,
        "production_ready": False,
    }


def _report(
    version: str,
    commit: str,
    checks: Sequence[Mapping[str, object]],
    evidence: Mapping[str, object],
) -> JsonObject:
    failed = [cast(str, check["check_id"]) for check in checks if check["passed"] is not True]
    return {
        "report_version": version,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "code_commit": commit,
        "diff_base": DIFF_BASE,
        "validation_profile": VALIDATION_PROFILE,
        "checks": list(checks),
        "check_count": len(checks),
        "evidence": dict(evidence),
        "production_boundary": "ENGINEERING_CANDIDATE_NOT_UAT_NOT_PRODUCTION_READY",
        "issues": failed,
        "status": "PASS" if not failed else "FAIL",
    }


def run_checks(
    root: Path,
    *,
    manifest_path: Path,
    browser_report_path: Path,
    sca_report_path: Path,
    license_report_path: Path,
    runtime_report_path: Path,
    release_output: Path,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    root = root.resolve(strict=True)
    commit = _git_head(root)
    distribution = inspect_frontend_distribution(
        root, manifest_path, expected_commit=commit
    )
    client = check_generated_client(root, expected_commit=commit)
    browser = check_browser_security(
        root,
        browser_report_path,
        sca_report_path,
        license_report_path,
        expected_commit=commit,
    )
    backend = check_backend_only(
        root,
        runtime_report_path,
        release_output,
        expected_commit=commit,
    )
    distribution_report = _report(
        "p8-frontend-distribution-report.v1",
        commit,
        (
            {"check_id": "archive-checksum-and-manifest", "passed": True},
            {"check_id": "deterministic-dual-assembly", "passed": True},
            {"check_id": "relative-static-hosting", "passed": True},
            {"check_id": "no-backend-core-demo-extension-or-source-map", "passed": True},
        ),
        distribution,
    )
    client_report = _report(
        "p8-frontend-client-isolation-report.v1",
        commit,
        (
            {"check_id": "p8-07-openapi-generated-snapshot", "passed": True},
            {"check_id": "five-public-operations-only", "passed": True},
            {"check_id": "canonical-json-byte-preservation", "passed": True},
            {"check_id": "in-memory-auth-and-no-store", "passed": True},
            {"check_id": "no-internal-or-extension-import", "passed": True},
        ),
        client,
    )
    browser_report = _report(
        "p8-frontend-browser-security-report.v1",
        commit,
        (
            {"check_id": "chromium-core-workflow", "passed": True},
            {"check_id": "auth-error-version-negative-matrix", "passed": True},
            {"check_id": "bilingual-keyboard-and-axe", "passed": True},
            {"check_id": "exact-lock-sca-and-license", "passed": True},
            {"check_id": "no-credential-persistence-or-ambient-cookie", "passed": True},
        ),
        browser,
    )
    backend_report = _report(
        "p8-frontend-backend-only-report.v1",
        commit,
        (
            {"check_id": "verified-runtime-release", "passed": True},
            {"check_id": "zero-frontend-payload", "passed": True},
            {"check_id": "isolated-wheel-liveness-readiness-openapi", "passed": True},
            {"check_id": "no-static-frontend-route", "passed": True},
        ),
        backend,
    )
    return distribution_report, client_report, browser_report, backend_report


def _write(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _failure_report(version: str, commit: str, error: Exception) -> JsonObject:
    code = getattr(error, "code", type(error).__name__)
    message = getattr(error, "message", "P8-11 validation failed")
    return {
        "report_version": version,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "code_commit": commit,
        "diff_base": DIFF_BASE,
        "validation_profile": VALIDATION_PROFILE,
        "checks": [],
        "check_count": 0,
        "evidence": {},
        "production_boundary": "ENGINEERING_CANDIDATE_NOT_UAT_NOT_PRODUCTION_READY",
        "issues": [{"code": str(code), "message": str(message)}],
        "status": "FAIL",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--distribution-manifest", type=Path, required=True)
    parser.add_argument("--browser-report", type=Path, required=True)
    parser.add_argument("--sca-report", type=Path, required=True)
    parser.add_argument("--license-report", type=Path, required=True)
    parser.add_argument("--runtime-report", type=Path, required=True)
    parser.add_argument("--release-output", type=Path, required=True)
    parser.add_argument("--distribution-report", type=Path, required=True)
    parser.add_argument("--client-report", type=Path, required=True)
    parser.add_argument("--browser-security-report", type=Path, required=True)
    parser.add_argument("--backend-only-report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    versions = (
        "p8-frontend-distribution-report.v1",
        "p8-frontend-client-isolation-report.v1",
        "p8-frontend-browser-security-report.v1",
        "p8-frontend-backend-only-report.v1",
    )
    outputs = (
        arguments.distribution_report,
        arguments.client_report,
        arguments.browser_security_report,
        arguments.backend_only_report,
    )
    commit = "unknown"
    try:
        resolved_root = arguments.root.resolve(strict=True)
        commit = _git_head(resolved_root)
        reports = run_checks(
            resolved_root,
            manifest_path=arguments.distribution_manifest,
            browser_report_path=arguments.browser_report,
            sca_report_path=arguments.sca_report,
            license_report_path=arguments.license_report,
            runtime_report_path=arguments.runtime_report,
            release_output=arguments.release_output,
        )
    except Exception as error:  # one sanitized, fail-closed evidence family
        reports = tuple(_failure_report(version, commit, error) for version in versions)
    for path, report in zip(outputs, reports, strict=True):
        _write(path, report)
    status = "PASS" if all(report["status"] == "PASS" for report in reports) else "FAIL"
    print(f"{status} {TASK_ID}: reports={len(reports)}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
