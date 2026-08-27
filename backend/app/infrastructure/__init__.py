"""Infrastructure adapters for the P0 engineering skeleton.

Importing this package never opens a database or Redis connection.
"""

from .config import DataPlane, RuntimeEnvironment, Settings, load_settings
from .audit_repository import SqlAlchemyAuditRepository
from .export_job_repository import SqlAlchemyExportJobRepository, StoredExportJob
from .execution_event_repository import SqlAlchemyExecutionEventRepository
from .publication_repository import (
    PublicationPersistenceResult,
    SqlAlchemyPublicationRepository,
)
from .replan_persistence import (
    ArtifactReference,
    ProjectionCheckpoint,
    ReplanAttemptReference,
    ReplanAuditAction,
    ReplanAuditRecord,
    ReplanResultReference,
    build_replan_attempt,
    build_replan_audit_record,
    build_replan_result,
)
from .replan_repository import (
    CheckpointWriteResult,
    SqlAlchemyProjectionCheckpointRepository,
    SqlAlchemyReplanAuditRepository,
    SqlAlchemyReplanLineageRepository,
    SqlAlchemyReplanRequestRepository,
    StoredProjectionCheckpoint,
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
    "ArtifactReference",
    "CheckpointWriteResult",
    "CurrentPublicationReference",
    "DataPlane",
    "PersistenceFailure",
    "ProjectionCheckpoint",
    "PublicationPersistenceResult",
    "ReplanAttemptReference",
    "ReplanAuditAction",
    "ReplanAuditRecord",
    "ReplanResultReference",
    "RuntimeEnvironment",
    "Settings",
    "SqlAlchemyAuditRepository",
    "SqlAlchemyExportJobRepository",
    "SqlAlchemyExecutionEventRepository",
    "SqlAlchemyProjectionCheckpointRepository",
    "SqlAlchemyPublicationRepository",
    "SqlAlchemyReplanAuditRepository",
    "SqlAlchemyReplanLineageRepository",
    "SqlAlchemyReplanRequestRepository",
    "SqlAlchemyScheduleVersionRepository",
    "StoredExportJob",
    "StoredProjectionCheckpoint",
    "StoredScheduleVersion",
    "WorkspaceDataPlane",
    "WorkspacePersistenceError",
    "build_replan_attempt",
    "build_replan_audit_record",
    "build_replan_result",
    "load_settings",
]
