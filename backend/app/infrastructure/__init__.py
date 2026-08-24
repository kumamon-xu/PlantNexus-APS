"""Infrastructure adapters for the P0 engineering skeleton.

Importing this package never opens a database or Redis connection.
"""

from .config import DataPlane, RuntimeEnvironment, Settings, load_settings
from .audit_repository import SqlAlchemyAuditRepository
from .export_job_repository import SqlAlchemyExportJobRepository, StoredExportJob
from .publication_repository import (
    PublicationPersistenceResult,
    SqlAlchemyPublicationRepository,
)
from .schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
    StoredScheduleVersion,
)
from .workspace_persistence import (
    CurrentPublicationReference,
    PersistenceFailure,
    WorkspaceDataPlane,
    WorkspacePersistenceError,
)

__all__ = [
    "CurrentPublicationReference",
    "DataPlane",
    "PersistenceFailure",
    "PublicationPersistenceResult",
    "RuntimeEnvironment",
    "Settings",
    "SqlAlchemyAuditRepository",
    "SqlAlchemyExportJobRepository",
    "SqlAlchemyPublicationRepository",
    "SqlAlchemyScheduleVersionRepository",
    "StoredExportJob",
    "StoredScheduleVersion",
    "WorkspaceDataPlane",
    "WorkspacePersistenceError",
    "load_settings",
]
