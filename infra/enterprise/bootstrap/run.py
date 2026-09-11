"""Validated process launch with deployment-only Secret injection."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import hmac
import io
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import quote

from .preflight import BootstrapError, Prepared, prepare


class RedactedStream(io.TextIOBase):
    """Buffer complete lines so fragmented writes cannot bypass redaction."""

    def __init__(self, target, values: tuple[str, ...]):
        self.target = target
        self.values = tuple(
            sorted(
                {
                    v
                    for value in values
                    for s in value.splitlines()
                    for v in (s, quote(s, safe=""))
                    if v
                },
                key=len,
                reverse=True,
            )
        )
        self.pending = ""
        self.dropping = False

    def writable(self):
        return True

    def isatty(self):
        return False

    def write(self, value):
        for character in value:
            if character == "\n":
                line = "[REDACTED_OVERSIZE]" if self.dropping else self.pending
                for secret in self.values:
                    line = line.replace(secret, "[REDACTED]")
                self.target.write(line + "\n")
                self.pending, self.dropping = "", False
            elif not self.dropping:
                self.pending += character
                if len(self.pending) > 8192:
                    self.pending, self.dropping = "", True
        return len(value)

    def flush(self):
        self.target.flush()


class LocalTestIdentity:
    """Explicit opaque test token; no JWT/OIDC or Production authority claim."""

    def __init__(self, prepared: Prepared):
        self.prepared = prepared

    def verify(self, bearer_token: str):
        from app.application.host_authorization import VerifiedHostIdentity

        p = self.prepared
        if not hmac.compare_digest(bearer_token.encode(), p.token.encode()):
            return None
        now = datetime.now(timezone.utc).replace(microsecond=0)
        return VerifiedHostIdentity.create(
            subject_ref=p.env["IDENTITY_SUBJECT"],
            identity_provider_reference=p.authorization.identity_provider_reference,
            issuer=p.authorization.issuer,
            audience=p.authorization.audience,
            issued_at_utc=now.isoformat().replace("+00:00", "Z"),
            expires_at_utc=(
                now
                + timedelta(
                    seconds=min(60, p.authorization.max_assertion_lifetime_seconds)
                )
            )
            .isoformat()
            .replace("+00:00", "Z"),
        )


def launch(prepared: Prepared, role: str) -> Any:
    # No inherited PLANTNEXUS setting can silently override the checked graph.
    for key in list(os.environ):
        if key.upper().startswith("PLANTNEXUS_"):
            del os.environ[key]
    for key, value in prepared.settings.model_dump().items():
        if value is not None:
            raw = (
                value.get_secret_value()
                if hasattr(value, "get_secret_value")
                else str(value)
            )
            os.environ["PLANTNEXUS_" + key.upper()] = raw
    # The legacy modules construct a default graph at import. Import with the
    # health-only defaults, close that graph, then use the checked explicit settings.
    if role == "api":
        import uvicorn

        saved = {
            k: os.environ.pop(k)
            for k in list(os.environ)
            if k.startswith("PLANTNEXUS_")
        }
        try:
            from app.api.app import app, create_runtime_app

            async def close_default():
                async with app.router.lifespan_context(app):
                    pass

            asyncio.run(close_default())
        finally:
            os.environ.update(saved)
        application = create_runtime_app(
            prepared.settings,
            host_identity_provider=LocalTestIdentity(prepared),
            host_authorization_policy=prepared.authorization,
            extension_artifacts=prepared.artifacts,
        )
        return uvicorn.run(
            application,
            host=prepared.env["API_BIND"],
            port=int(prepared.env["API_PORT"]),
            log_level=prepared.env["LOG_LEVEL"].lower(),
            access_log=False,
        )
    if role == "worker":
        saved = {
            k: os.environ.pop(k)
            for k in list(os.environ)
            if k.startswith("PLANTNEXUS_")
        }
        try:
            from app.jobs.celery_app import celery_app, create_runtime_celery_app

            celery_app.close()
        finally:
            os.environ.update(saved)
        application = create_runtime_celery_app(
            prepared.settings, extension_artifacts=prepared.artifacts
        )
        return application.worker_main(
            [
                "worker",
                "--loglevel=" + prepared.env["LOG_LEVEL"],
                "--concurrency=" + prepared.env["WORKER_CONCURRENCY"],
            ]
        )
    if role == "migration":
        from alembic.config import Config
        from alembic import command

        return command.upgrade(Config("/opt/plantnexus/alembic.ini"), "head")
    if role == "validator":
        from app.planning.validation.problem_schedule_validator import (
            validate_problem_schedule,
        )

        if not callable(validate_problem_schedule):
            raise BootstrapError("ENTRYPOINT_UNAVAILABLE", "runtime")
        print(
            json.dumps(
                {"status": "PASS", "role": "validator", "scope": "entrypoint only"}
            )
        )
        return None
    raise BootstrapError("COMMAND_INVALID", "command")


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise BootstrapError("COMMAND_INVALID", "command")


def main(argv=None) -> int:
    parser = SafeParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--role", choices=("api", "worker", "migration", "validator"), default="api"
    )
    parser.add_argument("--check", action="store_true")
    try:
        args = parser.parse_args(argv)
        prepared = prepare(args.config)
        if args.check:
            print(json.dumps(prepared.report()))
            return 0
        sys.stdout = RedactedStream(sys.stdout, prepared.secrets)
        sys.stderr = RedactedStream(sys.stderr, prepared.secrets)
        result = launch(prepared, args.role)
        if isinstance(result, int) and result != 0:
            raise BootstrapError("STARTUP_FAILED", "runtime")
        return 0
    except BootstrapError as error:
        print(json.dumps({"status": "FAIL", "code": error.code, "field": error.field}))
    except Exception:
        print(
            json.dumps({"status": "FAIL", "code": "STARTUP_FAILED", "field": "runtime"})
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
