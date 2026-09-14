"""Container-only deployment metadata gate. Never requires a host Python runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, "/opt/enterprise")
CONFIG_DIRECTORY = Path("/etc/plantnexus")


def require(value, code):
    if not value:
        raise ValueError(code)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def configuration_digest():
    entries = [
        (p.relative_to(CONFIG_DIRECTORY).as_posix(), digest(p))
        for p in sorted(CONFIG_DIRECTORY.rglob("*"))
        if p.is_file()
    ]
    require(entries, "CONFIGURATION_MISSING")
    return hashlib.sha256(
        json.dumps(entries, separators=(",", ":")).encode()
    ).hexdigest()


def environment(args, observed):
    from bootstrap.services import CONFIG, deployment_layout, prepare

    sys.path.insert(0, "/delivery")
    offline = Path("/delivery/MANIFEST.json").is_file()
    if offline:
        import importlib

        sys.path.insert(0, "/delivery/compose")
        control = importlib.import_module("control")
    else:
        from infra.enterprise.compose import control

    bundle, slot, project, port, mode, image = args
    require(mode in {"standalone", "enterprise"}, "MODE_INVALID")
    require(re.fullmatch(r"[a-z][a-z0-9-]{1,47}", project), "PROJECT_INVALID")
    require(port.isdigit() and 1024 <= int(port) <= 65535, "PORT_INVALID")
    for path in (bundle, slot):
        require(re.fullmatch(r"/[A-Za-z0-9_./-]+", path), "PATH_INVALID")
        require(".." not in Path(path).parts, "PATH_INVALID")
    report = read(
        Path(
            "/delivery/evidence/image-report.json"
            if offline
            else "/delivery/image-report.json"
        )
    )
    setattr(control, "inspect_image", lambda _: observed[0])
    control.image_identity(report, image)
    lines = Path("/delivery/SHA256SUMS").read_text().splitlines()
    archive_name = "images/runtime.tar" if offline else "image.tar"
    archive = [line.split()[0] for line in lines if line.endswith("  " + archive_name)]
    require(archive == [report["image_archive_sha256"]], "ARCHIVE_REPORT_MISMATCH")
    p = prepare(CONFIG)
    deployment_layout(p)
    if offline:
        m = read(Path("/delivery/MANIFEST.json"))
        require(
            m["schema_version"] == "enterprise-deployment-bundle.v1"
            and m["production_ready"] is False
            and m["status"] == "CANDIDATE",
            "BUNDLE_SCOPE_INVALID",
        )
        require(
            len(observed) == 1 and m["images"]["runtime"]["image_id"] == image,
            "IMAGE_IDENTITY_MISMATCH",
        )
        mapping = Path("/delivery/images/identities.tsv").read_text()
        require(
            mapping
            == "".join(
                n + " " + m["images"][n]["image_id"] + "\n"
                for n in ("runtime", "database", "redis")
            ),
            "IMAGE_MAPPING_INVALID",
        )
        locked = read(Path("/delivery/compose/dependencies.v1.json"))["images"]
        for n in ("database", "redis"):
            require(
                m["images"][n]["source_reference"] == locked[n]
                and control.digest_reference(locked[n])
                in m["images"][n]["repo_digests_at_export"],
                "DEPENDENCY_SOURCE_MISMATCH",
            )
            require(
                re.fullmatch(r"sha256:[0-9a-f]{64}", m["images"][n]["image_id"]),
                "IMAGE_ID_INVALID",
            )
            require(
                [
                    line.split()[0]
                    for line in lines
                    if line.endswith("  images/" + n + ".tar")
                ]
                == [m["images"][n]["tar_sha256"]],
                "DEPENDENCY_ARCHIVE_MISMATCH",
            )
    else:
        locked = read(Path("/delivery/infra/enterprise/compose/dependencies.v1.json"))[
            "images"
        ]
        for name, inspect in zip(("database", "redis"), observed[1:], strict=True):
            require(
                control.digest_reference(locked[name]) in inspect.get("RepoDigests", [])
                and inspect["Os"] == "linux"
                and inspect["Architecture"] == "amd64",
                "DEPENDENCY_IDENTITY_MISMATCH",
            )
        require(len(observed) == 3, "DEPENDENCY_IDENTITY_MISSING")
    if mode == "standalone":
        require(
            p.env["DB_HOST"] == "database" and p.env["DB_PORT"] == "5432",
            "ENDPOINT_INVALID",
        )
        for prefix in ("REDIS", "BROKER", "RESULT"):
            require(
                p.env[prefix + "_HOST"] == "redis"
                and p.env[prefix + "_PORT"] == "6379",
                "ENDPOINT_INVALID",
            )
            require(
                Path(p.env[prefix + "_USER_FILE"]).read_bytes().rstrip(b"\n")
                == b"default",
                "ACL_INVALID",
            )
            require(
                Path(p.env[prefix + "_PASSWORD_FILE"]).read_bytes()
                == Path(p.env["REDIS_PASSWORD_FILE"]).read_bytes(),
                "ACL_INVALID",
            )
    public = dict(
        RUNTIME_IMAGE_ID=image,
        CONFIG_DIR=slot + "/config",
        SECRETS_DIR=slot + "/secrets",
        CPU_LIMIT=p.env["CPU_LIMIT"],
        MEMORY_MIB=p.env["MEMORY_MIB"],
        DB_NAME=p.env["DB_NAME"],
        API_HOST_PORT=port,
        RUNTIME_NETWORK=project + "-runtime",
        ISOLATED_NETWORK=str(mode == "standalone").lower(),
    )
    for key, value in public.items():
        require(re.fullmatch(r"[A-Za-z0-9_./:-]+", value), "ENVIRONMENT_INVALID")
        print(key + "=" + value)


def identity(directory):
    a, b = read(directory / "api.json"), read(directory / "worker.json")
    require(a == b, "API_WORKER_IDENTITY_MISMATCH")
    d = a["descriptor"]
    # Process descriptor contains only the frozen safe identity carrier.
    return {"configuration": a["configuration"], "descriptor": d}


def backup_metadata(directory, image, project):
    from bootstrap.services import HEAD

    return dict(
        schema_version="enterprise-backup.v1",
        status="PASS",
        image_id=image,
        source_project=project,
        migration_head=HEAD,
        identity=identity(directory),
        configuration_files_sha256=configuration_digest(),
        database_sha256=digest(directory / "database.dump"),
        redis_recovery="fresh broker; no queued-task replay claim",
        quiescence="API_AND_WORKER_STOPPED",
        production_ready=False,
    )


def verify_backup(directory, image, project):
    from bootstrap.services import HEAD

    m = read(directory / "metadata.json")
    require(
        m["schema_version"] == "enterprise-backup.v1" and m["status"] == "PASS",
        "BACKUP_INVALID",
    )
    require(
        m["quiescence"] == "API_AND_WORKER_STOPPED" and m["production_ready"] is False,
        "BACKUP_SCOPE_INVALID",
    )
    require(
        m["configuration_files_sha256"] == configuration_digest(),
        "BACKUP_CONFIGURATION_MISMATCH",
    )
    require(
        m["image_id"] == image and m["migration_head"] == HEAD,
        "BACKUP_IDENTITY_MISMATCH",
    )
    require(m["source_project"] != project, "ISOLATED_TARGET_REQUIRED")
    require(
        digest(directory / "database.dump") == m["database_sha256"],
        "BACKUP_CHECKSUM_MISMATCH",
    )
    require(m["identity"] == identity(directory), "BACKUP_DESCRIPTOR_MISMATCH")
    return m


def main():
    try:
        action, *args = sys.argv[1:]
        if action == "environment":
            environment(args, json.load(sys.stdin))
        elif action == "identity":
            print(json.dumps(identity(Path("/state")), sort_keys=True))
        elif action == "receipt":
            print(
                json.dumps(
                    {
                        "image_id": args[0],
                        "identity": identity(Path("/state")),
                        "configuration_files_sha256": configuration_digest(),
                    },
                    sort_keys=True,
                )
            )
        elif action == "metadata":
            print(json.dumps(backup_metadata(Path("/backup"), *args), sort_keys=True))
        elif action == "verify-backup":
            verify_backup(Path("/backup"), *args)
        elif action == "compare-restored":
            m = verify_backup(Path("/backup"), *args)
            require(
                identity(Path("/state")) == m["identity"], "RESTORED_IDENTITY_MISMATCH"
            )
        elif action == "logs":
            # Deliberately allowlist diagnostics; arbitrary application lines cannot leak.
            counts = {}
            for line in sys.stdin:
                for code in re.findall(r'"code":\s*"([A-Z_]{1,64})"', line):
                    if code not in {
                        "DEPLOYMENT_FAILED",
                        "API_UNREADY",
                        "NAMED_WORKER_UNREADY",
                        "DATABASE_UNREADY",
                        "REDIS_UNREADY",
                        "MIGRATION_HEAD_MISMATCH",
                        "EXTENSION_UNHEALTHY",
                        "VALIDATION_REJECTED",
                    }:
                        continue
                    counts[code] = counts.get(code, 0) + 1
            print(
                json.dumps(
                    {"schema_version": "enterprise-log-summary.v1", "codes": counts}
                )
            )
        else:
            raise ValueError("COMMAND_INVALID")
        return 0
    except Exception as error:
        category = type(error).__name__
        if category not in {
            "ValueError",
            "KeyError",
            "BootstrapError",
            "ModuleNotFoundError",
            "PermissionError",
            "FileNotFoundError",
            "DeploymentError",
        }:
            category = "RuntimeError"
        print(
            json.dumps(
                {"status": "FAIL", "code": "METADATA_GATE_FAILED", "category": category}
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
