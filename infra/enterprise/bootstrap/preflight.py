"""Deployment-owned, offline preflight. No application/client is constructed here."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import stat
from typing import Any
from urllib.parse import quote

SOURCE_SHA = "39149091859b35b1303002a237a3cf1344572773"
RUNTIME_FP = "sha256:09559ca7f22af19c3f2b5fbb7f802c8d681574007fa31b2b8709ce5754b1083e"
KIT_FP = "sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361"
RUNTIME_ROOT = Path("/opt/plantnexus")
GROUPS = {
    "identity": "ENVIRONMENT DATA_PLANE RUNTIME_SOURCE_SHA RUNTIME_FINGERPRINT KIT_VERSION KIT_FINGERPRINT",
    "policy": "PLANNING_POLICY_FILE SOLVE_LIMITS_FILE HTTP_POLICY_FILE AUTHORIZATION_POLICY_FILE",
    "authorization": "IDENTITY_PROVIDER IDENTITY_ISSUER IDENTITY_AUDIENCE IDENTITY_CLIENT_ID IDENTITY_SUBJECT IDENTITY_TOKEN_FILE",
    "transport": "API_DOMAIN API_BIND API_PORT TLS_CERT_FILE TLS_KEY_FILE",
    "operations": "DATA_VOLUME BACKUP_VOLUME CPU_LIMIT MEMORY_MIB WORKER_CONCURRENCY LOG_LEVEL HEARTBEAT_SECONDS LEASE_SECONDS",
    "extension": "EXTENSION_MODE",
}
for _endpoint in ("DB", "REDIS", "BROKER", "RESULT"):
    GROUPS[_endpoint.lower()] = " ".join(
        f"{_endpoint}_{suffix}"
        for suffix in (
            "HOST",
            "PORT",
            "NAME" if _endpoint == "DB" else "INDEX",
            "USER_FILE",
            "PASSWORD_FILE",
        )
    )
EXTENSION_FIELDS = set(
    "EXTENSION_LOCK_FILE EXTENSION_CATALOG_FILE EXTENSION_KEY_ID EXTENSION_KEY_FILE".split()
)
REQUIRED = {name for group in GROUPS.values() for name in group.split()}
FIELDS = REQUIRED | EXTENSION_FIELDS
PLACEHOLDER = re.compile(r"__REQUIRED__|REPLACE_ME|CHANGEME|\$\{|<[^>]+>", re.I)


class BootstrapError(RuntimeError):
    def __init__(self, code: str, name: str):
        self.code = code
        self.field = (
            name
            if name
            in FIELDS
            | {
                "configuration",
                "runtime",
                "extension",
                "authorization",
                "tls",
                "command",
            }
            else "configuration"
        )
        super().__init__(f"{code}:{self.field}")


def fail(name: str, code: str = "CONFIGURATION_INVALID") -> None:
    raise BootstrapError(code, name)


def readonly(path: Path) -> bool:
    # The CLI has no bypass. Linux bind-mount read-only status is authoritative.
    if os.name != "posix":
        return False
    return bool(getattr(os, "statvfs")(path).f_flag & getattr(os, "ST_RDONLY"))


def read_file(value: str | Path, name: str, *, limit: int = 1024 * 1024) -> bytes:
    try:
        path = Path(value)
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
            fail(name, "UNSAFE_FILE")
        info = path.stat()
        if (
            not stat.S_ISREG(info.st_mode)
            or not 0 < info.st_size <= limit
            or not readonly(path)
        ):
            fail(name, "READONLY_FILE_REQUIRED")
        raw = path.read_bytes()
        if len(raw) != info.st_size:
            fail(name, "FILE_CHANGED")
        return raw
    except (OSError, ValueError):
        raise BootstrapError("FILE_UNAVAILABLE", name) from None


def strict_json(raw: bytes, name: str) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail(name)
            result[key] = value
        return result

    try:
        value = json.loads(
            raw, object_pairs_hook=pairs, parse_constant=lambda _: fail(name)
        )
        if not isinstance(value, dict) or PLACEHOLDER.search(raw.decode("utf-8")):
            fail(name)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise BootstrapError("DOCUMENT_INVALID", name) from None


def parse_env(raw: bytes) -> dict[str, str]:
    try:
        result = {}
        for line in raw.decode("utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if name not in FIELDS or name in result or not separator:
                fail("configuration")
            if (
                not value
                or value != value.strip()
                or PLACEHOLDER.search(value)
                or any(ord(c) < 32 for c in value)
                or value.startswith(('"', "'"))
            ):
                fail(name, "MISSING_OR_PLACEHOLDER")
            result[name] = value
        for name in sorted(REQUIRED - result.keys()):
            fail(name, "MISSING_OR_PLACEHOLDER")
        return result
    except UnicodeError:
        raise BootstrapError("CONFIGURATION_INVALID", "configuration") from None


def number(env: dict[str, str], name: str, low: int, high: int) -> int:
    value = env[name]
    if not re.fullmatch(r"[0-9]+", value) or not low <= int(value) <= high:
        fail(name)
    return int(value)


def secret(env: dict[str, str], name: str, *, minimum: int = 1) -> str:
    raw = read_file(env[name], name, limit=4096)
    try:
        value = raw.decode("utf-8").removesuffix("\n")
        if (
            not minimum <= len(value.encode()) <= 4096
            or PLACEHOLDER.search(value)
            or any(ord(c) < 33 or ord(c) == 127 for c in value)
        ):
            fail(name, "SECRET_INVALID")
        return value
    except UnicodeError:
        raise BootstrapError("SECRET_INVALID", name) from None


@dataclass(repr=False)
class Prepared:
    env: dict[str, str] = field(repr=False)
    settings: Any = field(repr=False)
    authorization: Any = field(repr=False)
    token: str = field(repr=False)
    secrets: tuple[str, ...] = field(repr=False)
    artifacts: tuple[Any, ...] = field(default=(), repr=False)

    def report(self) -> dict[str, Any]:
        return {
            "status": "PASS",
            "schema_version": "enterprise-preflight.v1",
            "runtime_source_sha": SOURCE_SHA,
            "runtime_fingerprint": RUNTIME_FP,
            "kit_version": "1.0.0",
            "kit_fingerprint": KIT_FP,
            "extension_count": len(self.artifacts),
            "environment": "TEST",
            "data_plane": "SIMULATION",
            "production_ready": False,
            "secrets_in_report": False,
            "nonsecret_configuration_fingerprint": fingerprint(
                json.dumps(self.env, sort_keys=True, separators=(",", ":")).encode()
            ),
            "issues": [],
        }


def prepare(path: Path) -> Prepared:
    env = parse_env(read_file(path, "configuration", limit=65536))
    exact = {
        "ENVIRONMENT": "test",
        "DATA_PLANE": "simulation",
        "RUNTIME_SOURCE_SHA": SOURCE_SHA,
        "RUNTIME_FINGERPRINT": RUNTIME_FP,
        "KIT_VERSION": "1.0.0",
        "KIT_FINGERPRINT": KIT_FP,
        "IDENTITY_PROVIDER": "LOCAL_TEST_TOKEN",
        "IDENTITY_CLIENT_ID": "not-applicable-local-test",
    }
    for name, expected in exact.items():
        if env[name] != expected:
            fail(name, "UNSUPPORTED_IDENTITY")
    release = strict_json(
        read_file(RUNTIME_ROOT / "metadata/release-manifest.json", "runtime"), "runtime"
    )
    if (
        release.get("code_commit") != SOURCE_SHA
        or release.get("release_fingerprint") != RUNTIME_FP
    ):
        fail("runtime", "UNSUPPORTED_IDENTITY")
    for name in (
        "IDENTITY_ISSUER",
        "IDENTITY_AUDIENCE",
        "IDENTITY_CLIENT_ID",
        "IDENTITY_SUBJECT",
    ):
        if not re.fullmatch(r"[!-~]{1,256}", env[name]):
            fail(name)
    endpoints, secrets = {}, []
    for prefix, setting in (
        ("DB", "database_url"),
        ("REDIS", "redis_url"),
        ("BROKER", "celery_broker_url"),
        ("RESULT", "celery_result_backend_url"),
    ):
        host = env[prefix + "_HOST"]
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}", host):
            fail(prefix + "_HOST")
        port = number(env, prefix + "_PORT", 1, 65535)
        user = secret(env, prefix + "_USER_FILE")
        password = secret(env, prefix + "_PASSWORD_FILE", minimum=16)
        secrets.extend((user, password))
        database = (
            env["DB_NAME"]
            if prefix == "DB"
            else str(number(env, prefix + "_INDEX", 0, 15))
        )
        if prefix == "DB" and not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,62}", database):
            fail("DB_NAME")
        scheme = "postgresql+psycopg" if prefix == "DB" else "redis"
        endpoints[setting] = (
            f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{database}"
        )
    if (
        len(
            {
                endpoints[n]
                for n in ("redis_url", "celery_broker_url", "celery_result_backend_url")
            }
        )
        != 3
    ):
        fail("REDIS_INDEX")
    number(env, "API_PORT", 1, 65535)
    number(env, "MEMORY_MIB", 128, 1048576)
    number(env, "WORKER_CONCURRENCY", 1, 256)
    heartbeat = number(env, "HEARTBEAT_SECONDS", 1, 3600)
    lease = number(env, "LEASE_SECONDS", 2, 86400)
    if lease <= heartbeat:
        fail("LEASE_SECONDS")
    try:
        if not Decimal("0.01") <= Decimal(env["CPU_LIMIT"]) <= Decimal("256"):
            fail("CPU_LIMIT")
        ipaddress.ip_address(env["API_BIND"])
    except (ValueError, ArithmeticError):
        raise BootstrapError("CONFIGURATION_INVALID", "CPU_LIMIT") from None
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}", env["API_DOMAIN"]):
        fail("API_DOMAIN")
    paths = [Path(env[n]) for n in ("DATA_VOLUME", "BACKUP_VOLUME")]
    if any(not p.is_absolute() or str(p) == p.anchor or ".." in p.parts for p in paths):
        fail("DATA_VOLUME")
    if paths[0].is_relative_to(paths[1]) or paths[1].is_relative_to(paths[0]):
        fail("BACKUP_VOLUME")
    read_file(env["TLS_CERT_FILE"], "TLS_CERT_FILE")
    tls_key = read_file(env["TLS_KEY_FILE"], "TLS_KEY_FILE", limit=65536)
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(env["TLS_CERT_FILE"], env["TLS_KEY_FILE"], password="")
    except (OSError, ssl.SSLError):
        raise BootstrapError("TLS_INVALID", "tls") from None
    secrets.append(tls_key.decode("ascii", errors="replace"))
    token = secret(env, "IDENTITY_TOKEN_FILE", minimum=32)
    secrets.append(token)
    documents = {
        n: strict_json(read_file(env[n], n), n) for n in GROUPS["policy"].split()
    }
    # Import only pure configuration/contract consumers, never API/Worker modules.
    try:
        from app.infrastructure.config import Settings
        from app.application.host_authorization import HostAuthorizationPolicyCatalog
        from app.application.runtime_http_adapter import RuntimeHttpPolicyCatalog
        from app.jobs.runtime_adapters import FrozenPlanningArtifactCatalog

        policy = HostAuthorizationPolicyCatalog.create(
            documents["AUTHORIZATION_POLICY_FILE"]
        )
        if (
            policy.environment != "TEST"
            or policy.data_plane != "SIMULATION"
            or policy.issuer != env["IDENTITY_ISSUER"]
            or policy.audience != env["IDENTITY_AUDIENCE"]
            or policy.identity_provider_reference
            != "identity-provider:enterprise.local-test.v1"
            or env["IDENTITY_SUBJECT"] not in {g.subject_ref for g in policy.grants}
        ):
            fail("authorization")
        planning = FrozenPlanningArtifactCatalog.create(
            planning_policy=documents["PLANNING_POLICY_FILE"],
            solve_limits=documents["SOLVE_LIMITS_FILE"],
            data_plane="SIMULATION",
        )
        RuntimeHttpPolicyCatalog.create(
            documents["HTTP_POLICY_FILE"],
            planning_inputs={
                "planning_policy": planning.planning_policy_reference,
                "solve_limits": planning.solve_limits_reference,
            },
        )
        http_scopes = {
            (s["tenant_id"], s["factory_id"], s["planning_scope_id"])
            for s in documents["HTTP_POLICY_FILE"]["scopes"]
        }
        if any(
            (s.tenant_id, s.factory_id, s.planning_scope_id) not in http_scopes
            for g in policy.grants
            for s in g.scopes
        ):
            fail("authorization")
        values = {
            name: definition.default
            for name, definition in Settings.model_fields.items()
        }
        values.update(
            dict(
                runtime_environment="test",
                data_plane="simulation",
                code_commit=SOURCE_SHA,
                runtime_composition_enabled=True,
                simulation_api_enabled=True,
                runtime_artifact_fingerprint=RUNTIME_FP,
                developer_kit_version="1.0.0",
                developer_kit_fingerprint=KIT_FP,
                runtime_schema_directory=RUNTIME_ROOT / "schemas/json",
                runtime_planning_policy_path=Path(env["PLANNING_POLICY_FILE"]),
                runtime_solve_limits_path=Path(env["SOLVE_LIMITS_FILE"]),
                runtime_http_policy_path=Path(env["HTTP_POLICY_FILE"]),
                log_level=env["LOG_LEVEL"],
                job_heartbeat_seconds=heartbeat,
                job_lease_seconds=lease,
                **endpoints,
            )
        )
        settings = Settings(**values)
    except BootstrapError:
        raise
    except Exception:
        raise BootstrapError("POLICY_INVALID", "configuration") from None
    mode = env["EXTENSION_MODE"]
    present = EXTENSION_FIELDS & env.keys()
    artifacts: tuple[Any, ...] = ()
    if mode == "none":
        if present:
            fail("extension", "ATOMIC_GROUP_INVALID")
    elif mode == "local":
        if present != EXTENSION_FIELDS:
            fail("extension", "ATOMIC_GROUP_INVALID")
        key = secret(env, "EXTENSION_KEY_FILE", minimum=32)
        secrets.append(key)
        from .extensions import load_local_extensions

        artifacts = load_local_extensions(env, key)
        from pydantic import SecretStr

        settings = settings.model_copy(
            update={
                "runtime_extension_catalog_path": Path(env["EXTENSION_CATALOG_FILE"]),
                "runtime_extension_verification_key_id": env["EXTENSION_KEY_ID"],
                "runtime_extension_verification_key": SecretStr(key),
            }
        )
    else:
        fail("EXTENSION_MODE")
    return Prepared(
        env,
        settings,
        policy,
        token,
        tuple(secrets + list(endpoints.values())),
        artifacts,
    )


def fingerprint(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()
