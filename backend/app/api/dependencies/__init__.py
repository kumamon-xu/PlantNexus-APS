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

__all__ = [
    "AuthorizationAuditRecord",
    "AuthorizationAuditSink",
    "AuthorizationProvider",
    "NullAuthorizationAuditSink",
    "PrincipalContext",
    "UnavailableAuthorizationProvider",
    "authorize_request",
]
