"""Fresh audit observations; report the OpenAPI gap rather than repairing it."""

from fastapi.testclient import TestClient
from app.api.app import create_app
from app.infrastructure.config import Settings, RuntimeEnvironment

from typing import Any
import re
from sqlalchemy import inspect, text
from backend.tests.integration import test_p9_manual as manual_support

runtime = manual_support.runtime


def test_health_dependency_failure_and_recovery() -> None:
    def unavailable() -> None:
        raise RuntimeError("synthetic dependency unavailable")

    for probe, expected in ((unavailable, 503), (lambda: None, 200)):
        application = create_app(
            Settings(runtime_environment=RuntimeEnvironment.TEST),
            probes={"database": probe, "redis": lambda: None},
        )
        with TestClient(application) as client:
            assert client.get("/health/live").status_code == 200
            result = client.get("/health/ready")
            assert result.status_code == expected
            assert "RuntimeError" not in result.text


def test_empty_unauthenticated_requests_are_rejected_without_business_writes(
    runtime: Any,
) -> None:  # noqa: F811
    def business_counts() -> dict[str, int]:
        names = [
            name
            for name in inspect(runtime.db).get_table_names()
            if "audit" not in name
        ]
        with runtime.db.connect() as connection:
            return {
                name: connection.scalar(text('SELECT count(*) FROM "' + name + '"'))
                for name in names
            }

    before = business_counts()
    tested = set()
    for path, methods in runtime.app.openapi()["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for method, operation in methods.items():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            concrete = re.sub(r"\{[^}]+\}", "p9-audit-denied-resource", path)
            response = runtime.client.request(
                method.upper(), concrete, json={} if method == "post" else None
            )
            assert response.status_code in {401, 422}, (
                operation["operationId"],
                response.status_code,
                response.text,
            )
            if response.status_code == 422:
                # These empty carriers are deliberately malformed: this is
                # contract rejection, not proof of the authorization branch.
                document = response.json()
                if document.get("error_version") == "headless-error.v1":
                    assert document["action"] == "FIX_REQUEST"
                    assert document["retryability"] == "NOT_RETRYABLE"
                else:
                    assert document["error_version"] == "planning-workspace-error.v1"
                    assert "INVALID_REQUEST" in response.text
            tested.add(operation["operationId"])
    assert len(tested) == 32
    assert business_counts() == before
