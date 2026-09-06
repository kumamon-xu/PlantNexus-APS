"""FastAPI dependency adapters for the planning workspace."""

from app.api.dependencies.authorization import (
    AuthorizationAuditRecord,
    AuthorizationAuditSink,
    AuthorizationProvider,
    NullAuthorizationAuditSink,
    PrincipalContext,
    UnavailableAuthorizationProvider,
    authorize_request,
)
from app.api.dependencies.host_authorization import authorize_headless_request

__all__ = [
    "AuthorizationAuditRecord",
    "AuthorizationAuditSink",
    "AuthorizationProvider",
    "NullAuthorizationAuditSink",
    "PrincipalContext",
    "UnavailableAuthorizationProvider",
    "authorize_request",
    "authorize_headless_request",
]
