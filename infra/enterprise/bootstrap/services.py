"""Compose roles and probes over the immutable Runtime; no Core modifications."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import socket
import ssl
import sys

from .preflight import BootstrapError, Prepared, prepare, read_file, strict_json
from .run import RedactedStream, launch

CONFIG = Path("/etc/plantnexus/deployment.env")
HEAD = "0009_host_authorization_audit"
DESCRIPTOR = Path("/tmp/runtime-descriptor.json")


def require(condition, code):
    if not condition:
        raise BootstrapError(code, "runtime")


def deployment_layout(p: Prepared):
    require(
        p.env["API_BIND"] == "0.0.0.0" and p.env["API_PORT"] == "8000",
        "COMPOSE_LAYOUT_INVALID",
    )
    require(
        p.env["DATA_VOLUME"] == "/var/lib/plantnexus"
        and p.env["BACKUP_VOLUME"] == "/var/backups/plantnexus",
        "COMPOSE_LAYOUT_INVALID",
    )


def database(p):
    from sqlalchemy import create_engine

    return create_engine(
        p.settings.database_url.get_secret_value(),
        connect_args={"connect_timeout": 2},
        pool_pre_ping=True,
    )


def dependencies(p: Prepared, *, exact_head: bool = True):
    from redis import Redis
    from sqlalchemy import text

    engine = database(p)
    try:
        with engine.connect() as connection:
            require(
                connection.execute(text("SELECT 1")).scalar() == 1, "DATABASE_UNREADY"
            )
            if exact_head:
                require(
                    connection.execute(text("SELECT version_num FROM alembic_version"))
                    .scalars()
                    .all()
                    == [HEAD],
                    "MIGRATION_HEAD_MISMATCH",
                )
    finally:
        engine.dispose()
    for field in ("redis_url", "celery_broker_url", "celery_result_backend_url"):
        client = Redis.from_url(
            getattr(p.settings, field).get_secret_value(),
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        try:
            require(client.ping() is True, "REDIS_UNREADY")
        finally:
            client.close()


def migrate(p: Prepared):
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect, text

    dependencies(p, exact_head=False)
    config = Config("/opt/plantnexus/alembic.ini")
    config.set_main_option("script_location", "/opt/plantnexus/backend/migrations")
    config.set_main_option(
        "sqlalchemy.url", p.settings.database_url.get_secret_value().replace("%", "%%")
    )
    script = ScriptDirectory.from_config(config)
    require(script.get_heads() == [HEAD], "RELEASE_HEAD_MISMATCH")
    engine = database(p)
    try:
        with engine.begin() as connection:
            if not inspect(connection).has_table("alembic_version"):
                # Published revisions exceed Alembic's default VARCHAR(32).
                # Same deployment bootstrap used by the frozen operations target.
                connection.execute(
                    text(
                        "CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL PRIMARY KEY)"
                    )
                )
            revisions = (
                connection.execute(text("SELECT version_num FROM alembic_version"))
                .scalars()
                .all()
            )
            require(
                len(revisions) <= 1 and all(script.get_revision(r) for r in revisions),
                "MIGRATION_HEAD_MISMATCH",
            )
        command.upgrade(config, "head")
    finally:
        engine.dispose()
    dependencies(p)


def record_descriptor(p, descriptor):
    DESCRIPTOR.write_text(
        json.dumps(
            {
                "configuration": p.report()["nonsecret_configuration_fingerprint"],
                "descriptor": descriptor.document,
            }
        ),
        encoding="utf-8",
    )


def descriptor(p):
    value = json.loads(DESCRIPTOR.read_text(encoding="utf-8"))
    require(
        value["configuration"] == p.report()["nonsecret_configuration_fingerprint"],
        "PROCESS_CONFIGURATION_DRIFT",
    )
    d = value["descriptor"]
    require(
        d["code_commit"] == p.env["RUNTIME_SOURCE_SHA"], "PROCESS_IDENTITY_MISMATCH"
    )
    r = d["runtime_resolution"]
    require(
        r["runtime_artifact_fingerprint"] == p.env["RUNTIME_FINGERPRINT"]
        and r["developer_kit_fingerprint"] == p.env["KIT_FINGERPRINT"],
        "PROCESS_IDENTITY_MISMATCH",
    )
    return d


def worker_health(p):
    from celery import Celery

    app = Celery(
        "enterprise-health", broker=p.settings.celery_broker_url.get_secret_value()
    )
    try:
        replies = app.control.ping(destination=["aps@aps-worker"], timeout=3)
        require(replies == [{"aps@aps-worker": {"ok": "pong"}}], "NAMED_WORKER_UNREADY")
    finally:
        app.close()


def api_health(p):
    context = ssl.create_default_context(cafile=p.env["TLS_CERT_FILE"])
    with socket.create_connection(("127.0.0.1", 8000), timeout=3) as raw:
        with context.wrap_socket(
            raw, server_hostname=p.env["API_DOMAIN"]
        ) as connection:
            connection.sendall(
                b"GET /health/ready HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
            )
            response = http.client.HTTPResponse(connection)
            response.begin()
            require(
                response.status == 200
                and json.loads(response.read(65536))["status"] == "UP",
                "API_UNREADY",
            )


def validate_inputs():
    from app.planning.validation.problem_schedule_validator import (
        validate_problem_schedule,
    )

    problem = strict_json(
        read_file(
            "/etc/plantnexus/validation/problem.json",
            "configuration",
            limit=16 * 1024 * 1024,
        ),
        "configuration",
    )
    candidate = strict_json(
        read_file(
            "/etc/plantnexus/validation/candidate.json",
            "configuration",
            limit=16 * 1024 * 1024,
        ),
        "configuration",
    )
    result = validate_problem_schedule(problem, candidate)
    # Business payload/violation entity IDs never enter deployment logs.
    print(
        json.dumps(
            {
                "status": result["status"],
                "role": "validator",
                "hard_violation_count": result["hard_violation_count"],
            }
        )
    )
    require(result["status"] == "PASS", "VALIDATION_REJECTED")


def main(argv=None):
    try:
        args = sys.argv[1:] if argv is None else argv
        require(
            len(args) == 1
            and args[0]
            in {
                "preflight",
                "migrate",
                "api",
                "worker",
                "validator",
                "health-api",
                "health-worker",
            },
            "COMMAND_INVALID",
        )
        role = args[0]
        p = prepare(CONFIG)
        deployment_layout(p)
        sys.stdout = RedactedStream(sys.stdout, p.secrets)
        sys.stderr = RedactedStream(sys.stderr, p.secrets)
        if role == "preflight":
            print(json.dumps(p.report()))
        elif role == "validator":
            validate_inputs()
        elif role == "migrate":
            migrate(p)
            print(json.dumps({"status": "PASS", "migration_head": HEAD}))
        else:
            dependencies(p)
            if role.startswith("health-"):
                descriptor(p)
                (api_health if role == "health-api" else worker_health)(p)
            else:
                result = launch(p, role, deployment=True)
                require(not isinstance(result, int) or result == 0, "PROCESS_FAILED")
        return 0
    except BootstrapError as error:
        print(json.dumps({"status": "FAIL", "code": error.code, "field": error.field}))
    except Exception:
        print(
            json.dumps(
                {"status": "FAIL", "code": "DEPLOYMENT_FAILED", "field": "runtime"}
            )
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
