"""P9 candidate delivery gate, consuming installed artifacts and retained bytes."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import site
import subprocess
import sys
from typing import Any, cast
import xml.etree.ElementTree as ET

from aps_developer_kit.check import _clean_install_and_cli, _security
from aps_developer_kit.contracts import (
    DeveloperKitContractError, plan_upgrade, require_compatible, verify_kit_archive,
)
from app.infrastructure.release.builder import (
    deterministic_archive, git_head, source_date_epoch,
)
from app.infrastructure.release.contracts import (
    ReleaseContractError, canonical_json_bytes, sha256_fingerprint, verify_release_archive,
)
from app.infrastructure.release.p9 import KIT, RUNTIME, build_candidate
from app.infrastructure.release.preflight import preflight_release


PREDECESSOR_SHA256 = "e45cc42ba4ee0e9ee032a8b7e7eae9c23db7bbbe6012e5f66d6cc46bb3d00a04"
FIELDS = ("developer_kit", "runtime", "extension_sdk", "extension_tooling", "enterprise_template")


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def run(command: list[str], *, cwd: Path, log: Path) -> None:
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    if result.returncode:
        raise RuntimeError(f"P9_DELIVERY_COMMAND_FAILED: {log.name}")


def installed_tests(root: Path, out: Path, python: Path, kit_root: Path) -> None:
    """Use source test drivers, while all product modules resolve to the new venv."""
    junit = out / "installed-runtime.xml"
    tests = [
        "backend/tests/integration/test_p9_delivery_install.py",
        "backend/tests/integration/test_p9_manual.py",
        "backend/tests/integration/test_p9_readmodel.py",
        "backend/tests/integration/test_p9_events.py",
        "backend/tests/integration/test_p9_replan.py",
        "backend/tests/integration/test_p9_consumers.py",
    ]
    bootstrap = out / "installed-driver.py"
    bootstrap.write_text(
        "import sys,pathlib,json,os\n"
        + f"sys.path.extend({[str(root), *site.getsitepackages()]!r})\n"
        + f"manifest=json.loads(pathlib.Path({str(kit_root / 'metadata/developer-kit-manifest.json')!r}).read_bytes())\n"
        + "os.environ['PLANTNEXUS_DEVELOPER_KIT_VERSION']=manifest['kit_version']\n"
        + "os.environ['PLANTNEXUS_DEVELOPER_KIT_FINGERPRINT']=manifest['release_fingerprint']\n"
        + "import app,aps_extension_sdk,aps_extension_tooling,pytest\n"
        + f"prefix=pathlib.Path({str(python.parent.parent)!r}).resolve()\n"
        + "for module in (app,aps_extension_sdk,aps_extension_tooling):\n"
        + " assert pathlib.Path(module.__file__).resolve().is_relative_to(prefix),module.__file__\n"
        + f"assert app.RUNTIME_VERSION == {RUNTIME!r}\n"
        + "assert app.SCHEMA_VERSION == '2.11.0'\n"
        + f"raise SystemExit(pytest.main({['-q', '-o', 'pythonpath=', '-k', 'not browser_real_runtime', '--junitxml=' + str(junit), *[str(root / p) for p in tests]]!r}))\n",
        encoding="utf-8", newline="\n",
    )
    run([str(python), "-I", str(bootstrap)], cwd=kit_root, log=out / "installed-runtime.log")
    document = ET.parse(junit).getroot()
    cases = document.findall(".//testcase")
    if not cases or document.findall(".//failure") or document.findall(".//error") or document.findall(".//skipped"):
        raise RuntimeError("P9_INSTALLED_RUNTIME_INCOMPLETE")
    write(out / "installed-runtime.json", {
        "status": "PASS", "runtime_version": RUNTIME,
        "tests": len(cases), "product_imports": "ISOLATED_INSTALLED_WHEELS",
        "junit_sha256": sha256_fingerprint(junit.read_bytes()), "issues": [],
    })


def database_phase(out: Path, python: Path, kit_root: Path, phase: str) -> None:
    """Upgrade retained populated 0009 data; rollback restores a stopped backup."""
    script = out / f"database-{phase}.py"
    runtime = kit_root.parent / "runtime/runtime"
    database = out / "upgrade-runtime.db"
    backup = out / "pre-upgrade-backup.db"
    source = f'''
from pathlib import Path
import json, shutil, sqlite3
from alembic.config import Config
from alembic import command
import app
phase={phase!r}
database=Path({str(database)!r})
backup=Path({str(backup)!r})
runtime=Path({str(runtime)!r})
assert app.RUNTIME_VERSION == ('0.2.0' if phase == 'upgrade' else '0.1.0')
cfg=Config(str(runtime/'alembic.ini'))
cfg.set_main_option('script_location',str(runtime/'backend/migrations'))
cfg.set_main_option('sqlalchemy.url','sqlite:///'+database.as_posix())
if phase == 'restore':
 shutil.copyfile(backup,database)
else:
 command.upgrade(cfg,'head')
with sqlite3.connect(database) as connection:
 revision=connection.execute('select version_num from alembic_version').fetchone()[0]
 assert revision == ('0010_runtime_replan' if phase == 'upgrade' else '0009_host_authorization_audit')
 if phase == 'before':
  connection.execute("INSERT INTO headless_authorization_audit_records (audit_event_id,data_plane,environment,operation_id,outcome,reason,actor_ref,scope_fingerprint,resource_reference,correlation_id,occurred_at_utc,audit_fingerprint,audit_json,audit_sha256) VALUES ('p9-delivery-preserved-audit','SIMULATION','TEST','getHeadlessPlanningRunStatus','ALLOWED','AUTHORIZED','actor:p9-delivery','sha256:' || ?,NULL,'p9-delivery','2026-09-21T00:00:00Z','sha256:' || ?,?,?)",('a'*64,'b'*64,b'{{}}','c'*64))
 count=connection.execute("select count(*) from headless_authorization_audit_records where audit_event_id='p9-delivery-preserved-audit'").fetchone()[0]
 assert count == 1
 assert connection.execute('pragma integrity_check').fetchone()[0] == 'ok'
 connection.commit()
if phase == 'before':
 shutil.copyfile(database,backup)
Path({str(out / ('database-' + phase + '.json'))!r}).write_text(json.dumps({{'status':'PASS','phase':phase,'runtime_version':app.RUNTIME_VERSION,'database_head':revision,'retained_audit_rows':count,'issues':[]}}),encoding='utf-8')
'''
    script.write_text(source, encoding="utf-8", newline="\n")
    run([str(python), "-I", str(script)], cwd=kit_root, log=out / f"database-{phase}.log")


def negative(expected: str, call: Any) -> str:
    try:
        call()
    except (DeveloperKitContractError, ReleaseContractError) as error:
        if error.code == expected:
            return error.code
        raise
    raise RuntimeError("P9_DELIVERY_NEGATIVE_ACCEPTED")


def check(root: Path, out: Path, predecessor: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=False)
    commit = git_head(root)
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=root,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if status:
        raise RuntimeError("P9_DELIVERY_REQUIRES_CLEAN_COMMITTED_INPUT")
    old_bytes = predecessor.read_bytes()
    if sha256(old_bytes).hexdigest() != PREDECESSOR_SHA256:
        raise RuntimeError("P9_PREDECESSOR_SOURCE_MISMATCH")
    old = verify_kit_archive(predecessor, expected_kit_version="1.0.1", channel="public-engineering")
    _clean_install_and_cli(
        predecessor, clean_projects=True, conformance_report=out / "predecessor-before-conformance.json",
        installed_check=lambda python, kit_root: database_phase(out, python, kit_root, "before"),
    )
    epoch = source_date_epoch(root, commit)
    first = build_candidate(root, out / "build-a", code_commit=commit, epoch=epoch)
    second = build_candidate(root, out / "build-b", code_commit=commit, epoch=epoch)
    for name in ("runtime", "kit"):
        if first[name].archive_path.read_bytes() != second[name].archive_path.read_bytes():
            raise RuntimeError("P9_BUILD_NONDETERMINISTIC")
    runtime, kit = first["runtime"], first["kit"]
    verified = verify_kit_archive(kit.archive_path, expected_kit_version=KIT, expected_code_commit=commit)
    verified_runtime = verify_release_archive(runtime.archive_path, expected_runtime_version=RUNTIME, expected_code_commit=commit)
    policy = json.loads(verified_runtime.files["policy/runtime-release-policy.v1.json"])
    configured = set(policy["preflight"]["required_configuration_names"])
    preflight = preflight_release(
        runtime.archive_path, expected_code_commit=commit,
        expected_runtime_version=RUNTIME, configured_names=configured,
    )
    preflight["negative_checks"] = {
        "wrong_source": negative("VERSION_MISMATCH", lambda: preflight_release(runtime.archive_path, expected_code_commit="0" * 40, expected_runtime_version=RUNTIME, configured_names=configured)),
        "missing_configuration": negative("CONFIGURATION_MISSING", lambda: preflight_release(runtime.archive_path, expected_code_commit=commit, expected_runtime_version=RUNTIME, configured_names=set())),
        "production": negative("PRODUCTION_AUTHORITY_UNAVAILABLE", lambda: preflight_release(runtime.archive_path, expected_code_commit=commit, expected_runtime_version=RUNTIME, configured_names=configured, production_requested=True)),
    }
    write(out / "runtime-preflight.json", preflight)
    for name in ("sdk", "tooling"):
        old_entry = cast(dict[str, Any], old.lock["artifacts"])[name]
        new_entry = cast(dict[str, Any], verified.lock["artifacts"])[name]
        if old.files[old_entry["path"]] != verified.files[new_entry["path"]]:
            raise RuntimeError("P9_UNCHANGED_COMPONENT_VERSION_HAS_DIFFERENT_BYTES")
    openapi = json.loads(verified_runtime.files["runtime/openapi/headless-api.v1.json"])
    operations = sorted(
        operation["operationId"] for path in openapi["paths"].values()
        for operation in path.values() if isinstance(operation, dict) and "operationId" in operation
    )
    if len(operations) != 34 or len(set(operations)) != 34:
        raise RuntimeError("P9_ARTIFACT_OPERATION_INVENTORY_INCOMPLETE")
    write(out / "operation-artifact-inventory.json", {
        "status": "PASS", "code_commit": commit, "runtime_sha256": runtime.archive_sha256,
        "openapi_sha256": sha256_fingerprint(verified_runtime.files["runtime/openapi/headless-api.v1.json"]),
        "operation_ids": operations, "sdk_and_tooling_retained_bytes": True, "issues": [],
    })
    current = {key: cast(dict[str, str], old.manifest["versions"])[key] for key in FIELDS}
    target = {key: cast(dict[str, str], verified.manifest["versions"])[key] for key in FIELDS}
    rejections = {
        "implicit_upgrade": negative("KIT_IMPLICIT_UPGRADE_FORBIDDEN", lambda: plan_upgrade(verified.compatibility, current, target, explicit_opt_in=False)),
        "mixed_runtime": negative("KIT_COMBINATION_UNSUPPORTED", lambda: require_compatible(verified.compatibility, {**target, "runtime": "0.1.0"})),
        "floating_runtime": negative("KIT_COMBINATION_UNSUPPORTED", lambda: require_compatible(verified.compatibility, {**target, "runtime": "latest"})),
        "public_channel": negative("KIT_SIGNATURE_REQUIRED", lambda: verify_kit_archive(kit.archive_path, channel="public-engineering")),
        "production_channel": negative("KIT_SIGNATURE_REQUIRED", lambda: verify_kit_archive(kit.archive_path, channel="production")),
    }
    upgrade = plan_upgrade(verified.compatibility, current, target, explicit_opt_in=True)
    def verify_install(python: Path, kit_root: Path) -> None:
        database_phase(out, python, kit_root, "upgrade")
        installed_tests(root, out, python, kit_root)

    _clean_install_and_cli(
        kit.archive_path, installed_check=verify_install, clean_projects=True,
        conformance_report=out / "candidate-installed-conformance.json",
    )
    security = _security(root, verified)
    write(out / "security.json", security)
    if security["status"] != "PASS":
        raise RuntimeError("P9_DELIVERY_SUPPLY_CHAIN_FAILED")
    # Restore the original artifact selection, then install and replay it again.
    _clean_install_and_cli(
        predecessor, clean_projects=True, conformance_report=out / "predecessor-restored-conformance.json",
        installed_check=lambda python, kit_root: database_phase(out, python, kit_root, "restore"),
    )
    if predecessor.read_bytes() != old_bytes:
        raise RuntimeError("P9_PREDECESSOR_MUTATED")
    deployment = {
        "contract": "p9-engineering-deployment-lock.v1", "code_commit": commit,
        "runtime": {"version": RUNTIME, "archive": runtime.archive_path.name, "sha256": runtime.archive_sha256},
        "developer_kit": {"version": KIT, "archive": kit.archive_path.name, "sha256": kit.archive_sha256, "fingerprint": kit.release_fingerprint},
        "database": "0010_runtime_replan", "schema_set": "2.11.0",
        "automatic_upgrade": False, "production_authorized": False,
        "rollback": {"kit_sha256": "sha256:" + PREDECESSOR_SHA256, "database": "RESTORE_PRE_UPGRADE_BACKUP", "downgrade_is_lossless": False},
    }
    bundle_files = {
        "deployment-lock.json": canonical_json_bytes(deployment) + b"\n",
        "runtime/" + runtime.archive_path.name: runtime.archive_path.read_bytes(),
        "kit/" + kit.archive_path.name: kit.archive_path.read_bytes(),
        "docs/deployment.md": (root / "docs/operations/deployment.md").read_bytes(),
        "docs/upgrade-and-rollback.md": (root / "docs/operations/developer-kit-release-upgrade-and-rollback.md").read_bytes(),
    }
    bundle = deterministic_archive("plantnexus-aps-p9-deployment-0.2.0", bundle_files, epoch=epoch)
    bundle_path = out / "deployment" / sha256(bundle).hexdigest() / "plantnexus-aps-p9-deployment-0.2.0.tar.gz"
    bundle_path.parent.mkdir(parents=True)
    bundle_path.write_bytes(bundle)
    bundle_path.with_name(bundle_path.name + ".sha256").write_text(
        f"{sha256(bundle).hexdigest()}  {bundle_path.name}\n", encoding="utf-8", newline="\n",
    )
    write(out / "deployment-lock.json", deployment)
    report = {
        "report_version": "p9-delivery.v1", "status": "PASS", "code_commit": commit,
        "task_id": "TASK-P9-10", "test_id": "TEST-P9-DELIVERY-001",
        "runtime": {key: str(value) if isinstance(value, Path) else value for key, value in asdict(runtime).items()},
        "kit": {key: str(value) if isinstance(value, Path) else value for key, value in asdict(kit).items()},
        "deployment_sha256": sha256_fingerprint(bundle), "reproducible": True,
        "predecessor_sha256": "sha256:" + PREDECESSOR_SHA256,
        "predecessor_replay_before_and_after": "PASS", "upgrade": upgrade,
        "rejections": rejections, "issues": [],
    }
    write(out / "delivery.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--predecessor", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output directory already exists; retained evidence must not be modified")
    try:
        check(args.root.resolve(), args.out.resolve(), args.predecessor.resolve())
    except Exception as error:
        write(args.out / "failure.json", {"status": "FAIL", "error_type": type(error).__name__, "error": str(error)})
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
