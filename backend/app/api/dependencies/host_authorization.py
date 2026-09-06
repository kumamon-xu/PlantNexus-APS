"""FastAPI projection for the P8 server-owned host authorization port."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from app.api.contracts import public_http_error
from app.application.host_authorization import (
    AuthorizedHostPrincipal,
    HostAuthorizationError,
    HostAuthorizationPort,
    HostAuthorizationReason,
    HostAuthorizationRequest,
)


def authorize_headless_request(
    request: Request,
    authorization: HostAuthorizationRequest,
) -> AuthorizedHostPrincipal:
    """Authorize one exact public operation before any application lookup."""

    adapter = getattr(request.app.state, "host_authorization_adapter", None)
    if adapter is None or not callable(getattr(adapter, "authorize", None)):
        raise public_http_error(
            "SERVICE_UNAVAILABLE",
            correlation_id=authorization.correlation_id,
            field="authorization",
            status_code=503,
        )
    try:
        return cast(HostAuthorizationPort, adapter).authorize(
            request.headers.get("Authorization"), authorization
        )
    except HostAuthorizationError as error:
        reason = (
            "PERSISTENCE_FAILED"
            if error.reason is HostAuthorizationReason.AUDIT_PERSISTENCE_FAILED
            else "AUTHORIZATION_DENIED"
        )
        raise public_http_error(
            reason,
            correlation_id=authorization.correlation_id,
            field="authorization",
            status_code=error.status_code,
        ) from None
    except Exception:
        raise public_http_error(
            "SYSTEM_ERROR",
            correlation_id=authorization.correlation_id,
            field="authorization",
            status_code=500,
        ) from None


__all__ = ["authorize_headless_request"]
