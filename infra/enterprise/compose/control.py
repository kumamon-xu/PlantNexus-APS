"""Host-side Compose identity gate; consumes approved image evidence, never pulls."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROLES = {"migrate", "api", "worker", "validator"}
SOURCE = "39149091859b35b1303002a237a3cf1344572773"


class DeploymentError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise DeploymentError(code)


def execute(command, *, env=None, timeout=180):
    result = subprocess.run(
        command, env=env, capture_output=True, timeout=timeout, check=False
    )
    return result


def inspect_image(reference):
    result = execute(["docker", "image", "inspect", reference])
    require(result.returncode == 0, "LOCAL_IMAGE_UNAVAILABLE")
    return json.loads(result.stdout)[0]


def digest_reference(reference):
    name, digest = reference.split("@", 1)
    if name.rfind(":") > name.rfind("/"):
        name = name.rsplit(":", 1)[0]
    return name + "@" + digest


def image_identity(report, reference):
    require(
        report.get("status") == "PASS"
        and not report.get("issues")
        and report.get("candidate") is False
        and report.get("dirty") is False,
        "IMAGE_EVIDENCE_INVALID",
    )
    require(
        re.fullmatch(r"sha256:[0-9a-f]{64}", report.get("image_id", "")),
        "IMAGE_EVIDENCE_INVALID",
    )
    require(
        reference == report["image_id"]
        or reference == report["tag"]
        or re.fullmatch(r"[a-z0-9./:_-]+@sha256:[0-9a-f]{64}", reference),
        "IMMUTABLE_REFERENCE_REQUIRED",
    )
    observed = inspect_image(reference)
    require(observed["Id"] == report["image_id"], "IMAGE_ID_MISMATCH")
    require(
        observed["Os"] == "linux"
        and observed["Architecture"] == "amd64"
        and observed["Config"]["User"] == "10001:10001",
        "IMAGE_PLATFORM_MISMATCH",
    )
    labels = observed["Config"]["Labels"]
    require(
        labels.get("org.opencontainers.image.revision") == report["code_commit"]
        and labels.get("io.plantnexus.aps.source-runtime-revision") == SOURCE,
        "IMAGE_LABEL_MISMATCH",
    )
    if "@sha256:" in reference:
        require(
            digest_reference(reference) in observed.get("RepoDigests", []),
            "REGISTRY_MAPPING_MISMATCH",
        )
    return observed["Id"]


def read_env(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        require(separator and key not in values, "CONFIGURATION_INVALID")
        values[key] = value
    return values


def render(*, report, reference, mode, config_dir, secrets_dir, project, port):
    require(
        mode in {"enterprise", "standalone"}
        and re.fullmatch(r"[a-z][a-z0-9-]{1,47}", project),
        "TARGET_INVALID",
    )
    require(1 <= port <= 65535, "PORT_INVALID")
    for directory in (config_dir, secrets_dir):
        require(
            directory.is_absolute()
            and directory.is_dir()
            and not directory.is_symlink(),
            "INPUT_DIRECTORY_INVALID",
        )
    identity = image_identity(report, reference)
    values = read_env(config_dir / "deployment.env")
    require(
        values.get("ENVIRONMENT") == "test"
        and values.get("DATA_PLANE") == "simulation",
        "TEST_SIMULATION_REQUIRED",
    )
    if mode == "standalone":
        require(
            values["DB_HOST"] == "database" and values["DB_PORT"] == "5432",
            "STANDALONE_ENDPOINT_MISMATCH",
        )
        for prefix in ("REDIS", "BROKER", "RESULT"):
            require(
                values[prefix + "_HOST"] == "redis"
                and values[prefix + "_PORT"] == "6379",
                "STANDALONE_ENDPOINT_MISMATCH",
            )
            require(
                (secrets_dir / (prefix.lower() + "_user")).read_bytes().rstrip(b"\n")
                == b"default",
                "STANDALONE_ACL_MISMATCH",
            )
            require(
                (secrets_dir / (prefix.lower() + "_password"))
                .read_bytes()
                .rstrip(b"\n")
                == (secrets_dir / "redis_password").read_bytes().rstrip(b"\n"),
                "STANDALONE_ACL_MISMATCH",
            )
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    env.update(
        {
            "RUNTIME_IMAGE_ID": identity,
            "CONFIG_DIR": str(config_dir),
            "SECRETS_DIR": str(secrets_dir),
            "CPU_LIMIT": values["CPU_LIMIT"],
            "MEMORY_MIB": values["MEMORY_MIB"],
            "DB_NAME": values["DB_NAME"],
            "API_HOST_PORT": str(port),
            "RUNTIME_NETWORK": project + "-runtime",
            "ISOLATED_NETWORK": str(mode == "standalone").lower(),
        }
    )
    command = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(config_dir / "deployment.env"),
        "-f",
        str(HERE / "docker-compose.enterprise.yml"),
    ]
    if mode == "standalone":
        command += ["-f", str(HERE / "docker-compose.standalone.yml")]
    result = execute(
        command + ["--profile", "validator", "config", "--format", "json"], env=env
    )
    require(result.returncode == 0, "COMPOSE_CONFIG_INVALID")
    document = json.loads(result.stdout)
    services = document["services"]
    require(
        set(services)
        == (ROLES | ({"database", "redis"} if mode == "standalone" else set())),
        "SERVICE_SET_INVALID",
    )
    for name, service in services.items():
        require(
            not service.get("build") and service["pull_policy"] == "never",
            "PREBUILT_IMAGE_REQUIRED",
        )
        if name in ROLES:
            require(
                service["image"] == identity
                and service["read_only"] is True
                and not service.get("environment"),
                "RUNTIME_CONFIGURATION_INVALID",
            )
    if mode == "standalone":
        locked = json.loads(
            (HERE / "dependencies.v1.json").read_text(encoding="utf-8")
        )["images"]
        for name, image in locked.items():
            require(services[name]["image"] == image, "DEPENDENCY_IDENTITY_MISMATCH")
            observed = inspect_image(image)
            require(
                digest_reference(image) in observed.get("RepoDigests", [])
                and observed["Os"] == "linux"
                and observed["Architecture"] == "amd64",
                "DEPENDENCY_IDENTITY_MISMATCH",
            )
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("config", "up"))
    parser.add_argument("--mode", choices=("enterprise", "standalone"), required=True)
    parser.add_argument("--image-report", type=Path, required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--secrets-dir", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.image_report.read_text(encoding="utf-8"))
        document = render(
            report=report,
            reference=args.reference,
            mode=args.mode,
            config_dir=args.config_dir,
            secrets_dir=args.secrets_dir,
            project=args.project,
            port=args.port,
        )
        if args.action == "config":
            require(args.output is not None, "OUTPUT_REQUIRED")
            args.output.write_text(json.dumps(document, indent=2), encoding="utf-8")
        else:
            with tempfile.TemporaryDirectory(prefix="enterprise-compose-") as temp:
                path = Path(temp) / "compose.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                command = [
                    "docker",
                    "compose",
                    "--project-name",
                    args.project,
                    "-f",
                    str(path),
                ]
                running = execute(command + ["ps", "--status", "running", "--services"])
                require(
                    running.returncode == 0
                    and not ROLES.intersection(running.stdout.decode().split()),
                    "RUNNING_TARGET_REQUIRES_CONTROLLED_STOP",
                )
                preflight = execute(
                    command
                    + [
                        "run",
                        "--rm",
                        "--no-deps",
                        "migrate",
                        "python",
                        "-m",
                        "bootstrap.services",
                        "preflight",
                    ]
                )
                require(preflight.returncode == 0, "CONFIGURATION_PREFLIGHT_FAILED")
                started = execute(
                    command
                    + ["up", "-d", "--wait", "--wait-timeout", "150", "api", "worker"],
                    timeout=240,
                )
                require(started.returncode == 0, "COMPOSE_START_FAILED")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "mode": args.mode,
                    "image_id": report["image_id"],
                    "pull_performed": False,
                    "production_ready": False,
                }
            )
        )
        return 0
    except DeploymentError as error:
        print(json.dumps({"status": "FAIL", "code": str(error)}))
    except Exception:
        print(json.dumps({"status": "FAIL", "code": "DEPLOYMENT_GATE_FAILED"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
