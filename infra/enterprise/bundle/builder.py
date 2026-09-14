"""Build-side assembler. Operator archives contain no build tooling or checkout."""

from __future__ import annotations

import gzip
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

from infra.enterprise.bundle.verify import (
    canonical,
    fingerprint,
    parse,
    require,
    safe_path,
    sha,
    verify,
)
from infra.enterprise.compose.control import digest_reference, image_identity

ROOT = Path(__file__).resolve().parents[3]


def command(args):
    result = subprocess.run(args, capture_output=True, check=False, timeout=1800)
    require(result.returncode == 0, "BUILD_COMMAND_FAILED")
    return result.stdout


def inspect(reference):
    return parse(command(["docker", "image", "inspect", reference]))[0]


def copy(source, target):
    require(source.is_file() and not source.is_symlink(), "INPUT_REGULAR_FILE_REQUIRED")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def image_config(archive, expected):
    with tarfile.open(archive, "r:") as stream:
        members = stream.getmembers()
        require(
            len(members) <= 4096 and len({m.name for m in members}) == len(members),
            "IMAGE_MEMBER_INVALID",
        )
        for member in members:
            safe_path(member.name.rstrip("/"))
            require(member.isfile() or member.isdir(), "IMAGE_LINK_REFUSED")
        manifest = stream.extractfile("manifest.json")
        if manifest is None:
            raise ValueError("IMAGE_MANIFEST_MISSING")
        entries = parse(manifest.read(1024 * 1024))
        require(len(entries) == 1, "SINGLE_IMAGE_REQUIRED")
        config = stream.extractfile(entries[0]["Config"])
        if config is None:
            raise ValueError("IMAGE_CONFIG_MISSING")
        data = config.read(1024 * 1024)
        import hashlib

        require(
            "sha256:" + hashlib.sha256(data).hexdigest() == expected,
            "IMAGE_CONFIG_ID_MISMATCH",
        )
        doc = parse(data)
        require(
            doc["os"] == "linux" and doc["architecture"] == "amd64",
            "IMAGE_PLATFORM_INVALID",
        )


def records(directory):
    result = []
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), "INPUT_SYMLINK_REFUSED")
        if path.is_dir():
            continue
        require(path.is_file(), "INPUT_REGULAR_FILE_REQUIRED")
        relative = safe_path(path.relative_to(directory).as_posix())
        if relative in {"MANIFEST.json", "SHA256SUMS"}:
            continue
        mode = 0o755 if relative.endswith(".sh") else 0o644
        result.append(
            dict(path=relative, bytes=path.stat().st_size, sha256=sha(path), mode=mode)
        )
    return sorted(result, key=lambda r: r["path"])


def seal(directory, identity, output):
    require(
        not output.exists() and not Path(str(output) + ".sha256").exists(),
        "OUTPUT_EXISTS",
    )
    payload = records(directory)
    m = dict(identity, members=payload, payload_fingerprint=fingerprint(payload))
    (directory / "MANIFEST.json").write_bytes(canonical(m))
    all_records = payload + [
        dict(path="MANIFEST.json", sha256=sha(directory / "MANIFEST.json"))
    ]
    (directory / "SHA256SUMS").write_text(
        "".join(
            r["sha256"] + "  " + r["path"] + "\n"
            for r in sorted(all_records, key=lambda r: r["path"])
        ),
        encoding="utf-8",
        newline="\n",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        output.open("xb") as raw,
        gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=1
        ) as compressed,
        tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as tar,
    ):
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            member = tarfile.TarInfo(
                directory.name + "/" + path.relative_to(directory).as_posix()
            )
            member.size = path.stat().st_size
            member.mode = 0o755 if path.suffix == ".sh" else 0o644
            with path.open("rb") as data:
                tar.addfile(member, data)
    digest = sha(output)
    result = verify(output, digest)
    Path(str(output) + ".sha256").write_text(
        digest + "  " + output.name + "\n", encoding="utf-8", newline="\n"
    )
    return result


def assemble(args):
    commit = command(["git", "rev-parse", "HEAD"]).decode().strip()
    dirty = bool(
        command(["git", "status", "--porcelain", "--untracked-files=normal"]).strip()
    )
    require(not dirty or args.candidate, "CLEAN_CHECKOUT_REQUIRED")
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "COMMIT_INVALID")
    staging = (ROOT / "build/enterprise-container/staging").resolve()
    output = args.output.resolve()
    require(
        output.is_relative_to(staging) and not output.exists(),
        "NEW_STAGING_DIRECTORY_REQUIRED",
    )
    output.mkdir(parents=True)
    directory = output / ("plantnexus-aps-enterprise-deployment-0.1.0-" + commit)
    directory.mkdir()
    report = parse(args.image_report.read_bytes())
    require(
        sha(args.runtime_archive) == report["image_archive_sha256"],
        "RUNTIME_TAR_MISMATCH",
    )
    image_identity(report, report["image_id"])
    inputs = parse((ROOT / "infra/enterprise/image-inputs.v1.json").read_bytes())
    require(
        report["source_runtime_sha"] == inputs["source_sha"]
        and report["source_archive_sha256"] == inputs["archive_sha256"],
        "FROZEN_SOURCE_MISMATCH",
    )
    require(
        sha(args.runtime_sbom) == report["security"]["sbom_sha256"],
        "RUNTIME_SBOM_MISMATCH",
    )
    images = {}
    images_dir = directory / "images"
    images_dir.mkdir()
    copy(args.runtime_archive, images_dir / "runtime.tar")
    image_config(images_dir / "runtime.tar", report["image_id"])
    images["runtime"] = dict(
        path="images/runtime.tar",
        image_id=report["image_id"],
        tar_sha256=report["image_archive_sha256"],
        platform="linux/amd64",
        source_reference=report["tag"],
        repo_digests_at_export=report["repo_digests"],
    )
    copy(args.image_report, directory / "evidence/image-report.json")
    copy(args.runtime_sbom, directory / "SBOM/runtime.cdx.json")
    locked = parse(
        (ROOT / "infra/enterprise/compose/dependencies.v1.json").read_bytes()
    )["images"]
    from scripts.enterprise_image_build import scan_image

    for name in ("database", "redis"):
        observed = inspect(locked[name])
        require(
            digest_reference(locked[name]) in observed.get("RepoDigests", [])
            and observed["Os"] == "linux"
            and observed["Architecture"] == "amd64",
            "DEPENDENCY_EXPORT_IDENTITY_INVALID",
        )
        archive = images_dir / (name + ".tar")
        command(["docker", "save", "--output", str(archive), observed["Id"]])
        image_config(archive, observed["Id"])
        scan_dir = output / (name + "-scan")
        scan_dir.mkdir()
        os.link(archive, scan_dir / archive.name)
        security = scan_image(scan_dir / archive.name, inputs, scan_dir)
        copy(
            scan_dir / "image-sbom.cdx.json", directory / ("SBOM/" + name + ".cdx.json")
        )
        # Raw vulnerabilities/license observations remain explicit, not a production waiver.
        (directory / ("evidence/" + name + "-security.json")).write_bytes(
            canonical(
                dict(
                    security,
                    scope="fixed-existing-dependency-inventory",
                    production_security_approval=False,
                )
            )
        )
        images[name] = dict(
            path="images/" + name + ".tar",
            image_id=observed["Id"],
            tar_sha256=sha(archive),
            platform="linux/amd64",
            source_reference=locked[name],
            repo_digests_at_export=observed["RepoDigests"],
        )
    mappings = []
    groups = {
        "bootstrap": (
            "scripts/bootstrap",
            [
                "__init__.py",
                "extensions.py",
                "preflight.py",
                "run.py",
                "services.py",
                "workspace.py",
            ],
        ),
        "scripts": (
            "scripts",
            [
                "common.sh",
                "metadata.py",
                "pg-client.sh",
                *[
                    a + ".sh"
                    for a in (
                        "preflight",
                        "install",
                        "start",
                        "status",
                        "logs",
                        "stop",
                        "backup",
                        "restore",
                        "rollback",
                    )
                ],
            ],
        ),
        "compose": (
            "compose",
            [
                "control.py",
                "dependencies.v1.json",
                "docker-compose.enterprise.yml",
                "docker-compose.standalone.yml",
                "redis-entrypoint.sh",
            ],
        ),
        "config": (
            "config",
            [
                ".env.example",
                "configuration-matrix.v1.json",
                "authorization-policy.example.json",
                "workspace-authorization-policy.example.json",
                "extension-catalog.example.json",
                "extension-lock.example.json",
                "planning-policy.example.json",
                "runtime-policy.example.json",
                "solve-limits.example.json",
                "reverse-proxy.example.conf",
                "secrets.example.yml",
            ],
        ),
    }
    for group, (target_group, names) in groups.items():
        for name in names:
            source = ROOT / "infra/enterprise" / group / name
            target = directory / target_group / name
            copy(source, target)
            transformations = []
            if name == "docker-compose.enterprise.yml":
                target.write_text(
                    source.read_text(encoding="utf-8").replace(
                        "source: ../bootstrap\n", "source: ../scripts/bootstrap\n"
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                transformations.append("bootstrap-relative-path")
            if name == "docker-compose.standalone.yml":
                text = source.read_text(encoding="utf-8")
                for role in ("database", "redis"):
                    require(
                        text.count(locked[role]) == 1,
                        "COMPOSE_SOURCE_REFERENCE_MISSING",
                    )
                    text = text.replace(locked[role], images[role]["image_id"])
                target.write_text(text, encoding="utf-8", newline="\n")
                transformations.append("pinned-registry-to-exported-image-id")
            mappings.append(
                dict(
                    source=source.relative_to(ROOT).as_posix(),
                    source_sha256=sha(source),
                    path=target.relative_to(directory).as_posix(),
                    sha256=sha(target),
                    transformations=transformations,
                )
            )
    (images_dir / "identities.tsv").write_text(
        "".join(
            n + " " + images[n]["image_id"] + "\n"
            for n in ("runtime", "database", "redis")
        ),
        encoding="utf-8",
        newline="\n",
    )
    copy(ROOT / "infra/enterprise/bundle/DEPLOYMENT.md", directory / "DEPLOYMENT.md")
    identity = dict(
        schema_version="enterprise-deployment-bundle.v1",
        status="CANDIDATE",
        signature_present=False,
        channel="unsigned-internal-test-only",
        production_ready=False,
        independent_acceptance="P8-28_REQUIRED",
        packaging_commit=commit,
        dirty=dirty,
        image_packaging_commit=report["code_commit"],
        runtime_source_commit=inputs["source_sha"],
        runtime_archive_sha256=inputs["archive_sha256"],
        runtime_fingerprint=inputs["release_fingerprint"],
        sdk_version="1.0.0",
        kit_version="1.0.0",
        kit_fingerprint="sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361",
        extension_policy="approved-readonly-server-inputs; no bundled enterprise artifact; original runtime verification required",
        offline_modes=["enterprise", "standalone"],
        tools=[
            "Linux x86_64",
            "Docker Engine >=27",
            "Compose >=2.30",
            "POSIX sh",
            "GNU coreutils",
            "awk",
            "find",
            "tar",
            "gzip",
        ],
        host_python_required=False,
        reverse_proxy="no additional container; loopback TLS API; external ingress is operator prerequisite",
        images=images,
        source_mappings=mappings,
        seal_order=[
            "payload",
            "MANIFEST.json excluding itself and SHA256SUMS",
            "SHA256SUMS excluding itself",
            "archive",
            "external sidecar",
        ],
        late_evidence="reseal and verify unchanged payload_fingerprint; executable changes require new acceptance",
    )
    result = seal(directory, identity, output / (directory.name + ".tar.gz"))
    require(
        command(["git", "rev-parse", "HEAD"]).decode().strip() == commit,
        "CHECKOUT_CHANGED_DURING_BUILD",
    )
    result.update(
        schema_version="enterprise-bundle-report.v1",
        code_commit=commit,
        task_id="TASK-P8-27",
        dirty=dirty,
        archive=str((output / (directory.name + ".tar.gz")).relative_to(ROOT)),
        candidate_directory=str(directory.relative_to(ROOT)),
    )
    return result
