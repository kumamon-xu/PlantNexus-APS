"""Reseal accepted bytes and clean only inventoried enterprise staging output."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import sys
import uuid
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra.enterprise.bundle.builder import seal  # noqa: E402
from infra.enterprise.bundle.verify import (  # noqa: E402
    canonical,
    extract,
    parse,
    require,
    sha,
    verify,
)
from infra.enterprise.acceptance.report import validate  # noqa: E402
from scripts.provider_evidence import load_reusable_manifest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STAGING = Path("build/enterprise-container/staging")
FINAL = Path("build/enterprise-container/final")
EVIDENCE = Path("build/validation/enterprise/P8-29")


def confined(root, path):
    """Check lexical and resolved containment, including Windows reparse points."""
    root = root.resolve()
    path = Path(os.path.abspath(path))
    require(path != root and path.is_relative_to(root), "PATH_OUTSIDE_ROOT")
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(
                not part.is_symlink()
                and not getattr(info, "st_file_attributes", 0) & 0x400,
                "LINK_OR_REPARSE_REFUSED",
            )
        if part == root:
            break
    require(path.resolve().is_relative_to(root), "RESOLVED_PATH_OUTSIDE_ROOT")
    return path


def bound(root, path):
    path = Path(path)
    return confined(root, path if path.is_absolute() else root / path)


def checked_json(path, expected):
    require(sha(path) == expected, "EVIDENCE_CHECKSUM_MISMATCH")
    return parse(path.read_bytes())


def provider(root, path, commit):
    value = parse(path.read_bytes())
    require(
        value["result"] == "PASS"
        and value["implementation_sha"] == commit
        and value["required_check"]["conclusion"] == "success",
        "PROVIDER_IDENTITY_INVALID",
    )
    require(bool(value["artifacts"]), "PROVIDER_ARTIFACTS_MISSING")
    for item in value["artifacts"]:
        archive = bound(root, path.parent / "artifacts" / item["archive_file"])
        require(sha(archive) == item["sha256"], "PROVIDER_ARCHIVE_CHANGED")
    require(
        load_reusable_manifest(
            path,
            path.parent / "artifacts",
            repository="kumamon-xu/PlantNexus-APS",
            workflow="ci.yml",
            commit_sha=commit,
            required_context="validate",
            app_id=15368,
        )
        is not None,
        "CANONICAL_PROVIDER_INVALID_OR_EXPIRED",
    )
    return dict(
        implementation_sha=commit,
        run_id=value["run"]["id"],
        manifest_sha256=sha(path),
        required_validate="success",
    )


def accepted(root, completion_path, expected):
    completion = checked_json(completion_path, expected)
    require(
        completion["task_id"] == "TASK-P8-28"
        and completion["status"] == "PASS"
        and completion["verdict"] == "READY"
        and completion["production_ready"] is False
        and completion["issues"] == [],
        "ACCEPTANCE_NOT_READY",
    )
    commit = completion["implementation_sha"]
    p = bound(root, completion["provider_manifest"])
    checked_json(p, completion["provider_manifest_sha256"])
    identity = provider(root, p, commit)
    receipt = checked_json(
        bound(root, completion["bundle_receipt"]), completion["bundle_receipt_sha256"]
    )
    require(
        receipt["status"] == "PASS"
        and receipt["implementation_sha"] == commit
        and receipt["provider_manifest_sha256"] == sha(p),
        "RECEIPT_BINDING_INVALID",
    )
    reports = p.parent / "extracted"
    values = {}
    for name in (
        "ci-enterprise-image-bundle.json",
        "ci-enterprise-image-acceptance.json",
    ):
        values[name] = checked_json(
            bound(root, reports / name), receipt["reports"][name]
        )
    bundle, acceptance = values.values()
    validate(acceptance, bundle, commit)
    source = confined(root / STAGING, bound(root, completion["candidate_archive"]))
    result = verify(source, completion["candidate_archive_sha256"])
    for key in ("payload_fingerprint", "images", "checksums_sha256", "manifest_sha256"):
        require(result[key] == completion[key] == bundle[key], "ACCEPTED_BYTES_CHANGED")
    require(
        result["archive_sha256"] == bundle["archive_sha256"], "ARCHIVE_BINDING_INVALID"
    )
    require(result["packaging_commit"] == commit, "PACKAGING_IDENTITY_INVALID")
    return source, result, identity


def install_commands():
    return (
        "\n".join(
            [
                'docker load --input "$BUNDLE/images/runtime.tar"',
                *[
                    f'sh "$BUNDLE/scripts/{action}.sh" "$BUNDLE" "$CHECKSUMS" "$RUNTIME" "$SLOT" "$PROJECT" "$PORT" "$MODE"'
                    for action in ("preflight", "install", "status")
                ],
            ]
        )
        + "\n"
    )


def finalize(root, completion, expected, handoff_provider, commit):
    source, before, acceptance_identity = accepted(root, completion, expected)
    handoff_identity = provider(root, handoff_provider, commit)
    target = bound(root, FINAL)
    require(not target.exists(), "FINAL_DIRECTORY_EXISTS")
    stage = bound(root, STAGING / ("finalize-" + uuid.uuid4().hex))
    stage.mkdir(parents=True)
    extracted = extract(source, before["archive_sha256"], stage / "unpacked")
    directory = stage / "unpacked" / extracted["root"]
    manifest = parse((directory / "MANIFEST.json").read_bytes())
    require(manifest.get("dirty") is False, "DIRTY_SOURCE")
    original_members = manifest["members"]
    index = dict(
        schema_version="enterprise-final-handoff-index.v1",
        status="UNSIGNED_INTERNAL_ENGINEERING_DELIVERY",
        production_ready=False,
        accepted_archive_sha256=before["archive_sha256"],
        payload_fingerprint=before["payload_fingerprint"],
        acceptance=acceptance_identity,
        finalizer=handoff_identity,
        acceptance_checks=30,
        scope="TEST/SIMULATION; unchanged operating payload; evidence-only reseal",
    )
    for name in ("handoff-index.json", "HANDOFF.md"):
        require(not (directory / "evidence" / name).exists(), "HANDOFF_ALREADY_PRESENT")
    (directory / "evidence/handoff-index.json").write_bytes(canonical(index))
    (directory / "evidence/HANDOFF.md").write_text(
        "# 最终内部企业部署交接\n\n"
        "本包已由 P8-28 独立双模式离线验收，30/30 PASS；P8-29仅补充证据并重封。\n"
        "DEPLOYMENT.md及MANIFEST中的候选/待验收文字是保留的原始格式，当前结论见handoff-index.json。\n"
        "运行payload、镜像、配置模板及原证据字节不变；仅TEST/SIMULATION，未签名，非Production Ready。\n"
        "包名保留已验收packaging SHA；finalizer SHA单独记录，不是新的Runtime或Kit版本。\n\n"
        "从可信交付报告核对归档SHA和sidecar，在新的空目录解包并核对SHA256SUMS。\n"
        "准备包外SLOT/config及SLOT/secrets，完成所有必填模板及独立工作区授权后，设置绝对BUNDLE/SLOT、PROJECT、PORT、MODE。\n"
        "RUNTIME取images/identities.tsv的runtime行；CHECKSUMS取已验证包内SHA256SUMS的SHA-256。\n\n"
        "```sh\n" + install_commands() + "```\n\n"
        "MODE为standalone或enterprise；后者需已准备专属隔离DB/Redis。无需源码、构建工具或联网下载。\n"
        "install已完成迁移和启动，status核验健康与身份；失败立即停止。备份/恢复命令和边界见DEPLOYMENT.md。\n",
        encoding="utf-8",
        newline="\n",
    )
    publish = stage / "publish"
    publish.mkdir()
    output = publish / source.name
    after = seal(directory, manifest, output)
    final_manifest = parse((directory / "MANIFEST.json").read_bytes())
    original_paths = {r["path"] for r in original_members}
    require(
        [r for r in final_manifest["members"] if r["path"] in original_paths]
        == original_members
        and after["payload_fingerprint"] == before["payload_fingerprint"]
        and after["images"] == before["images"],
        "PAYLOAD_DRIFT",
    )
    require(
        {r["path"] for r in final_manifest["members"]} - original_paths
        == {"evidence/handoff-index.json", "evidence/HANDOFF.md"},
        "UNEXPECTED_FINAL_MEMBER",
    )
    require(sha(source) == before["archive_sha256"], "SOURCE_CHANGED")
    publish.rename(target)
    result = dict(after)
    result.update(
        schema_version="enterprise-final-handoff.v1",
        task_id="TASK-P8-29",
        status="PASS",
        issues=[],
        production_ready=False,
        implementation_sha=commit,
        acceptance=acceptance_identity,
        finalizer=handoff_identity,
        source_archive_sha256=before["archive_sha256"],
        archive=(FINAL / source.name).as_posix(),
        sidecar_sha256=sha(target / (source.name + ".sha256")),
        payload_equivalent=True,
        original_members_preserved=len(original_members),
        added_members=["evidence/handoff-index.json", "evidence/HANDOFF.md"],
        install_commands=install_commands().splitlines(),
    )
    return result


def final_valid(root, receipt_path, expected):
    receipt = checked_json(receipt_path, expected)
    require(
        receipt["status"] == "PASS" and receipt["payload_equivalent"] is True,
        "FINAL_NOT_VALID",
    )
    archive = confined(root / FINAL, bound(root, receipt["archive"]))
    require(archive.parent == (root / FINAL).resolve(), "FINAL_PATH_INVALID")
    require(
        {p.name for p in archive.parent.iterdir()}
        == {archive.name, archive.name + ".sha256"},
        "FINAL_NOT_UNIQUE",
    )
    result = verify(archive, receipt["archive_sha256"])
    sidecar = Path(str(archive) + ".sha256")
    require(
        sha(sidecar) == receipt["sidecar_sha256"]
        and sidecar.read_bytes()
        == (result["archive_sha256"] + "  " + archive.name + "\n").encode(),
        "SIDECAR_INVALID",
    )
    return receipt


def inventory(root):
    staging = root / STAGING
    bound(root, staging)
    require(staging.is_dir(), "STAGING_MISSING")
    rows = []
    for path in sorted(staging.rglob("*")):
        confined(staging, path)
        info = path.lstat()
        require(
            stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
            "SPECIAL_FILE_REFUSED",
        )
        relative = path.relative_to(staging)
        scanner_cache = relative.as_posix().endswith(
            ("/trivy-cache/db/trivy.db", "/trivy-cache/fanal/fanal.db")
        )
        require(
            not {"data", "backups", "secrets", "volumes"}.intersection(
                p.lower() for p in relative.parts
            )
            and (
                scanner_cache
                or path.suffix.lower() not in {".db", ".sqlite", ".sqlite3", ".dump"}
            ),
            "RECOVERY_DATA_REFUSED",
        )
        row = dict(path=relative.as_posix(), directory=path.is_dir())
        if path.is_file():
            row.update(
                bytes=info.st_size,
                sha256=sha(path),
                preserve=not scanner_cache
                and not path.name.endswith((".tar", ".tar.gz", ".whl", ".zip")),
            )
        rows.append(row)
    return rows


def plan_cleanup(root, receipt, expected):
    final_valid(root, receipt, expected)
    return dict(
        schema_version="enterprise-cleanup-plan.v1",
        status="DRY_RUN",
        staging_root=str((root / STAGING).resolve()),
        final_receipt=str(receipt.resolve()),
        final_receipt_sha256=expected,
        preserve_root=str((root / EVIDENCE / "retained-staging").resolve()),
        entries=inventory(root),
        docker_cleanup=False,
    )


def apply_cleanup(root, plan_path, expected):
    plan = checked_json(plan_path, expected)
    require(
        plan["schema_version"] == "enterprise-cleanup-plan.v1"
        and plan["status"] == "DRY_RUN",
        "PLAN_INVALID",
    )
    require(
        plan["staging_root"] == str((root / STAGING).resolve()), "CLEANUP_ROOT_MISMATCH"
    )
    require(
        plan["preserve_root"] == str((root / EVIDENCE / "retained-staging").resolve()),
        "PRESERVE_ROOT_MISMATCH",
    )
    receipt = bound(root, plan["final_receipt"])
    final_valid(root, receipt, plan["final_receipt_sha256"])
    require(inventory(root) == plan["entries"], "STAGING_CHANGED_AFTER_PLAN")
    preserved = []
    for row in plan["entries"]:
        if row.get("preserve"):
            source = confined(root / STAGING, root / STAGING / row["path"])
            target = confined(
                root / EVIDENCE, root / EVIDENCE / "retained-staging" / row["path"]
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            require(sha(target) == row["sha256"], "PRESERVATION_FAILED")
            preserved.append(row["path"])
    require(inventory(root) == plan["entries"], "STAGING_CHANGED_BEFORE_DELETE")
    final_valid(root, receipt, plan["final_receipt_sha256"])
    targets = [confined(root / STAGING, p) for p in sorted((root / STAGING).iterdir())]
    # All absolute targets and every descendant were checked before any delete.
    # Only the authorized staging tree is touched; no Docker or global build clean.
    for path in targets:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    require(not list((root / STAGING).iterdir()), "STAGING_NOT_EMPTY")
    final_valid(root, receipt, plan["final_receipt_sha256"])
    return dict(
        schema_version="enterprise-cleanup-result.v1",
        status="PASS",
        issues=[],
        plan_sha256=expected,
        removed_absolute_roots=[str(p) for p in targets],
        preserved_files=preserved,
        staging_empty=True,
        docker_cleanup=False,
        production_ready=False,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("finalize")
    f.add_argument("--completion", type=Path, required=True)
    f.add_argument("--completion-sha256", required=True)
    f.add_argument("--provider", type=Path, required=True)
    f.add_argument("--commit", required=True)
    c = sub.add_parser("plan-cleanup")
    c.add_argument("--receipt", type=Path, required=True)
    c.add_argument("--receipt-sha256", required=True)
    a = sub.add_parser("apply-cleanup")
    a.add_argument("--plan", type=Path, required=True)
    a.add_argument("--plan-sha256", required=True)
    for item in (f, c, a):
        item.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    report = confined(ROOT / EVIDENCE, bound(ROOT, args.report))
    require(not report.exists(), "REPORT_EXISTS")
    try:
        if args.command == "finalize":
            require(
                subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
                .decode()
                .strip()
                == args.commit
                and not subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=ROOT
                ).strip(),
                "EXACT_CLEAN_FINALIZER_COMMIT_REQUIRED",
            )
            result = finalize(
                ROOT,
                bound(ROOT, args.completion),
                args.completion_sha256,
                bound(ROOT, args.provider),
                args.commit,
            )
        elif args.command == "plan-cleanup":
            result = plan_cleanup(ROOT, bound(ROOT, args.receipt), args.receipt_sha256)
        else:
            result = apply_cleanup(ROOT, bound(ROOT, args.plan), args.plan_sha256)
    except Exception as error:
        result = dict(
            status="FAIL",
            issues=[
                str(error) if isinstance(error, ValueError) else type(error).__name__
            ],
            production_ready=False,
        )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_bytes(canonical(result))
    print(result["status"])
    return 0 if result["status"] in {"PASS", "DRY_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
