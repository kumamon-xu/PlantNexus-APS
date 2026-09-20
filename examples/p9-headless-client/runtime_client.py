"""Public HTTP consumer; requires no PlantNexus package or Frontend installation."""

import json
from hashlib import sha256
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


class RuntimeFailure(Exception):
    def __init__(self, status: int | None, reason: str, correlation: str | None):
        super().__init__(f"Runtime {status}: {reason}; correlation={correlation}")
        self.status = status
        self.reason = reason


class RuntimeClient:
    """The host supplies short-lived credentials in memory and approved carriers."""

    def __init__(self, base_url: str, token: str):
        url = urlsplit(base_url)
        if url.scheme not in {"http", "https"} or url.username or url.password:
            raise ValueError("Use an explicit HTTP(S) Runtime URL without credentials")
        self.base_url = base_url.rstrip("/")
        self._token = token

    def request(
        self,
        method: str,
        path: str,
        document: dict[str, Any] | None = None,
        *,
        key: str | None = None,
        query: dict[str, Any] | None = None,
        compared_version: dict[str, Any] | None = None,
        planning_scope_id: str | None = None,
    ) -> dict[str, Any]:
        if not path.startswith("/api/v1/") or "://" in path:
            raise ValueError("Only formal Runtime API paths are accepted")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        carrier = document or query or {}
        correlation = carrier.get("correlation_id")
        if correlation:
            headers["X-Correlation-Id"] = correlation
        if key:
            headers["Idempotency-Key"] = key
        if planning_scope_id is not None:
            headers["X-Planning-Scope-Id"] = planning_scope_id
        if compared_version is not None:
            headers.update(
                {
                    "X-Compared-Schedule-Version-Id": compared_version[
                        "schedule_version_id"
                    ],
                    "X-Compared-State": compared_version["state"],
                    "X-Compared-Content-Fingerprint": compared_version[
                        "content_fingerprint"
                    ],
                }
            )
        if query:
            path += "?" + urlencode(
                {"query": json.dumps(query, ensure_ascii=False, allow_nan=False)}
            )
        body = None
        if document is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(document, ensure_ascii=False, allow_nan=False).encode(
                "utf-8"
            )
        try:
            with urlopen(
                Request(
                    self.base_url + path, data=body, headers=headers, method=method
                ),
                timeout=30,
            ) as response:
                value = json.load(response)
        except HTTPError as error:
            try:
                detail = json.load(error)
            except (ValueError, UnicodeError):
                detail = {}
            raise RuntimeFailure(
                error.code,
                str(
                    detail.get("details", {}).get(
                        "reason", detail.get("reason", "HTTP_ERROR")
                    )
                ),
                correlation,
            ) from None
        except (URLError, TimeoutError):
            raise RuntimeFailure(
                None,
                "UNKNOWN_OUTCOME" if method == "POST" else "SERVICE_UNAVAILABLE",
                correlation,
            ) from None
        if not isinstance(value, dict):
            raise RuntimeFailure(None, "CONTRACT_REJECTED", correlation)
        if correlation and value.get("correlation_id") != correlation:
            raise RuntimeFailure(None, "CORRELATION_MISMATCH", correlation)
        return value

    def submit(self, document: dict[str, Any], key: str) -> dict[str, Any]:
        if document.get("execution_event_version") == "execution-event.v1":
            path = "/api/v1/execution-events"
        elif document.get("replan_request_version") == "replan-request.v1":
            path = "/api/v1/replan-requests"
        else:
            raise ValueError("Unsupported submission carrier")
        return self.request("POST", path, document, key=key)

    def command(self, document: dict[str, Any]) -> dict[str, Any]:
        suffix = {
            "SUBMIT_FOR_REVIEW": "validate",
            "APPROVE": "approve",
            "REJECT": "reject",
            "PUBLISH": "publish",
        }.get(document["command_type"], "commands")
        source = quote(document["source_id"], safe="")
        return self.request(
            "POST",
            f"/api/v1/schedule-versions/{source}/{suffix}",
            document,
            key=document["idempotency_key"],
        )

    def version(self, identity: str) -> dict[str, Any]:
        response = self.request(
            "GET", f"/api/v1/schedule-versions/{quote(identity, safe='')}"
        )
        document = response.get("schedule_version", response)
        if document.get("schedule_version_id") != identity:
            raise RuntimeFailure(None, "IDENTITY_MISMATCH", None)
        schemas = {"schedule-version.v1": "2.6.0", "schedule-version.v2": "2.8.0"}
        if (
            document.get("schedule_version_version") not in schemas
            or document.get("schema_set_version")
            != schemas[document["schedule_version_version"]]
            or document.get("data_plane") != "SIMULATION"
            or document.get("environment") != "TEST"
        ):
            raise RuntimeFailure(None, "CONTRACT_REJECTED", None)
        content = json.dumps(
            document["content"],
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if document["content_fingerprint"] != "sha256:" + sha256(content).hexdigest():
            raise RuntimeFailure(None, "FINGERPRINT_MISMATCH", None)
        return document

    def control(
        self, document: dict[str, Any], key: str, planning_scope_id: str
    ) -> dict[str, Any]:
        if document.get("action") not in {"CANCEL", "RETRY"}:
            raise ValueError("Unsupported attempt action")
        identity = quote(document["request_id"], safe="")
        return self.request(
            "POST",
            f"/api/v1/replan-requests/{identity}/{document['action'].lower()}",
            document,
            key=key,
            planning_scope_id=planning_scope_id,
        )
