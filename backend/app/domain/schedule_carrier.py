"""Explicit version dispatch for immutable schedule lifecycle consumers."""

from collections.abc import Mapping

from app.domain.execution_contracts import require_p4_document
from app.domain.workspace_contracts import require_workspace_document


def require_schedule_carrier(document: Mapping[str, object]) -> str:
    if document.get("schedule_version_version") == "schedule-version.v2":
        return require_p4_document(document)
    return require_workspace_document(document)
