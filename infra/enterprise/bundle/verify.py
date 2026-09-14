"""Independent, bounded offline archive verification; no Docker or network access."""

from __future__ import annotations

from functools import partial
import hashlib
import json
from pathlib import PurePosixPath
import re
import tarfile

MAX_BYTES = 6 * 1024**3
MAX_MEMBERS = 1024
SHA = re.compile(r"[0-9a-f]{64}")
IMAGE = re.compile(r"sha256:[0-9a-f]{64}")
ACTIONS = (
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


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse(data):
    def invalid_constant(_):
        raise ValueError("NONFINITE_JSON")

    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)


def safe_path(name):
    require(
        isinstance(name, str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", name),
        "UNSAFE_PATH",
    )
    require(all(p not in {".", ".."} for p in name.split("/")), "UNSAFE_PATH")
    return name


def fingerprint(records):
    return hashlib.sha256(
        canonical([r for r in records if not r["path"].startswith("evidence/")])
    ).hexdigest()


def verify(archive, expected_sha):
    require(SHA.fullmatch(expected_sha), "EXPECTED_CHECKSUM_REQUIRED")
    require(
        archive.is_file() and not archive.is_symlink() and sha(archive) == expected_sha,
        "ARCHIVE_CHECKSUM_MISMATCH",
    )
    records, small, roots, seen = [], {}, set(), set()
    total = 0
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream:
            require(len(seen) < MAX_MEMBERS, "MEMBER_LIMIT")
            name = safe_path(member.name)
            require(name not in seen, "DUPLICATE_MEMBER")
            seen.add(name)
            parts = name.split("/")
            roots.add(parts[0])
            require(len(roots) == 1 and len(parts) > 1, "SINGLE_ROOT_REQUIRED")
            require(
                member.isfile() and not member.pax_headers and not member.sparse,
                "REGULAR_MEMBER_REQUIRED",
            )
            relative = "/".join(parts[1:])
            total += member.size
            require(
                0 <= member.size <= MAX_BYTES and total <= MAX_BYTES, "EXPANSION_LIMIT"
            )
            mode = 0o755 if relative.endswith(".sh") else 0o644
            require(
                member.mode == mode and member.uid == member.gid == member.mtime == 0,
                "MEMBER_METADATA_INVALID",
            )
            data = stream.extractfile(member)
            if data is None:
                raise ValueError("MEMBER_UNREADABLE")
            digest = hashlib.sha256()
            chunks = []
            size = 0
            for block in iter(partial(data.read, 1024 * 1024), b""):
                size += len(block)
                digest.update(block)
                if not relative.startswith("images/") or not relative.endswith(".tar"):
                    require(size <= 16 * 1024**2, "TEXT_SIZE_LIMIT")
                    chunks.append(block)
            require(size == member.size, "TRUNCATED_MEMBER")
            records.append(
                dict(path=relative, bytes=size, sha256=digest.hexdigest(), mode=mode)
            )
            if chunks:
                small[relative] = b"".join(chunks)
    records.sort(key=lambda r: r["path"])
    by_path = {r["path"]: r for r in records}
    require(
        {"MANIFEST.json", "SHA256SUMS", "DEPLOYMENT.md"} <= set(small), "SEAL_MISSING"
    )
    m = parse(small["MANIFEST.json"])
    require(m["schema_version"] == "enterprise-deployment-bundle.v1", "SCHEMA_INVALID")
    require(
        m["status"] == "CANDIDATE"
        and m["production_ready"] is False
        and m["signature_present"] is False,
        "SCOPE_INVALID",
    )
    require(m["independent_acceptance"] == "P8-28_REQUIRED", "ACCEPTANCE_NOT_PERFORMED")
    require(re.fullmatch(r"[0-9a-f]{40}", m["packaging_commit"]), "COMMIT_INVALID")
    root = next(iter(roots))
    require(
        root == "plantnexus-aps-enterprise-deployment-0.1.0-" + m["packaging_commit"],
        "ROOT_IDENTITY_MISMATCH",
    )
    payload = [r for r in records if r["path"] not in {"MANIFEST.json", "SHA256SUMS"}]
    require(m["members"] == payload, "INVENTORY_MISMATCH")
    require(
        m["payload_fingerprint"] == fingerprint(payload), "PAYLOAD_FINGERPRINT_MISMATCH"
    )
    checksums = "".join(
        r["sha256"] + "  " + r["path"] + "\n"
        for r in records
        if r["path"] != "SHA256SUMS"
    ).encode()
    require(small["SHA256SUMS"] == checksums, "CHECKSUM_INVENTORY_MISMATCH")
    require(
        set(m["images"]) == {"runtime", "database", "redis"}, "IMAGE_CLOSURE_MISSING"
    )
    for name, entry in m["images"].items():
        require(
            IMAGE.fullmatch(entry["image_id"]) and entry["platform"] == "linux/amd64",
            "IMAGE_IDENTITY_INVALID",
        )
        require(entry["path"] == "images/" + name + ".tar", "IMAGE_PATH_INVALID")
        require(
            by_path[entry["path"]]["sha256"] == entry["tar_sha256"],
            "IMAGE_TAR_MISMATCH",
        )
        require("SBOM/" + name + ".cdx.json" in small, "SBOM_MISSING")
        require(
            parse(small["SBOM/" + name + ".cdx.json"])["bomFormat"] == "CycloneDX",
            "SBOM_INVALID",
        )
    image_report = parse(small["evidence/image-report.json"])
    require(
        image_report["status"] == "PASS"
        and image_report["issues"] == []
        and image_report["candidate"] is False
        and image_report["dirty"] is False,
        "IMAGE_REPORT_INVALID",
    )
    require(
        image_report["image_id"] == m["images"]["runtime"]["image_id"]
        and image_report["image_archive_sha256"]
        == m["images"]["runtime"]["tar_sha256"],
        "RUNTIME_BINDING_INVALID",
    )
    require(
        m["runtime_source_commit"] == image_report["source_runtime_sha"],
        "SOURCE_BINDING_INVALID",
    )
    require(
        m["image_packaging_commit"] == image_report["code_commit"],
        "IMAGE_COMMIT_MISMATCH",
    )
    require(
        m["sdk_version"] == m["kit_version"] == "1.0.0"
        and m["kit_fingerprint"]
        == "sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361"
        and m["runtime_fingerprint"]
        == "sha256:09559ca7f22af19c3f2b5fbb7f802c8d681574007fa31b2b8709ce5754b1083e",
        "COMPATIBILITY_IDENTITY_INVALID",
    )
    require(m["offline_modes"] == ["enterprise", "standalone"], "MODE_CLOSURE_INVALID")
    required = {"scripts/" + action + ".sh" for action in ACTIONS}
    required |= {
        "scripts/common.sh",
        "scripts/metadata.py",
        "scripts/pg-client.sh",
        "scripts/bootstrap/__init__.py",
        "scripts/bootstrap/preflight.py",
        "scripts/bootstrap/services.py",
        "scripts/bootstrap/run.py",
        "scripts/bootstrap/extensions.py",
        "compose/control.py",
        "compose/dependencies.v1.json",
        "compose/docker-compose.enterprise.yml",
        "compose/docker-compose.standalone.yml",
        "compose/redis-entrypoint.sh",
        "config/.env.example",
        "config/configuration-matrix.v1.json",
        "images/identities.tsv",
    }
    require(required <= set(small), "DEPLOYMENT_MEMBER_MISSING")
    require(
        {p for p in by_path if p.endswith(".tar")}
        == {"images/runtime.tar", "images/database.tar", "images/redis.tar"},
        "UNEXPECTED_IMAGE_ARCHIVE",
    )
    ids = "".join(
        name + " " + m["images"][name]["image_id"] + "\n"
        for name in ("runtime", "database", "redis")
    )
    require(small["images/identities.tsv"] == ids.encode(), "IMAGE_MAPPING_INVALID")
    locked = parse(small["compose/dependencies.v1.json"])["images"]
    for name in ("database", "redis"):
        require(
            m["images"][name]["source_reference"] == locked[name],
            "DEPENDENCY_SOURCE_INVALID",
        )
        ref = (
            locked[name].split("@")[0].split(":")[0] + "@" + locked[name].split("@")[1]
        )
        require(
            ref in m["images"][name]["repo_digests_at_export"],
            "DEPENDENCY_DIGEST_MISSING",
        )
        require(
            ("image: " + m["images"][name]["image_id"]).encode()
            in small["compose/docker-compose.standalone.yml"],
            "COMPOSE_IMAGE_MAPPING_INVALID",
        )
    require(
        b"source: ../scripts/bootstrap"
        in small["compose/docker-compose.enterprise.yml"],
        "BOOTSTRAP_MAPPING_INVALID",
    )
    for path, data in small.items():
        require(b"\r" not in data, "LF_REQUIRED")
        require(
            not re.search(
                rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|://[^\s/:]+:[^\s/@]+@",
                data,
            ),
            "SECRET_DETECTED",
        )
        require(
            not any(
                p
                in {
                    ".git",
                    "__pycache__",
                    "backend",
                    "frontend",
                    "demo",
                    "secrets",
                    "backups",
                    "logs",
                    "node_modules",
                }
                for p in PurePosixPath(path).parts
            ),
            "FORBIDDEN_PAYLOAD",
        )
    return dict(
        schema_version="enterprise-bundle-verification.v1",
        status="PASS",
        archive_sha256=expected_sha,
        root=root,
        payload_fingerprint=m["payload_fingerprint"],
        manifest_sha256=by_path["MANIFEST.json"]["sha256"],
        checksums_sha256=by_path["SHA256SUMS"]["sha256"],
        member_count=len(records),
        expanded_bytes=total,
        images=m["images"],
        packaging_commit=m["packaging_commit"],
        production_ready=False,
        issues=[],
    )


def extract(archive, expected_sha, destination):
    result = verify(archive, expected_sha)
    require(
        not destination.exists() and not destination.is_symlink(),
        "NEW_EXTRACTION_DIRECTORY_REQUIRED",
    )
    require(
        all(not p.is_symlink() for p in (destination.parent, *destination.parents)),
        "EXTRACTION_PARENT_SYMLINK",
    )
    destination.mkdir()
    # No extractall: only files already verified; exclusive writes prevent overwrite.
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream:
            target = destination / safe_path(member.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = stream.extractfile(member)
            if source is None:
                raise ValueError("MEMBER_UNREADABLE")
            with target.open("xb") as output:
                for block in iter(partial(source.read, 1024 * 1024), b""):
                    output.write(block)
            target.chmod(member.mode)
    require(sha(archive) == expected_sha, "ARCHIVE_CHANGED_DURING_EXTRACTION")
    return result
