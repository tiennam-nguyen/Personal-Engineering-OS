"""Safe, typed errors exposed across PEOS boundaries."""

from __future__ import annotations


class PeosError(Exception):
    code = "peos_error"
    exit_code = 1

    def __init__(self, message: str, recovery_action: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.recovery_action = recovery_action


class ValidationError(PeosError):
    code = "validation_error"
    exit_code = 2


class WorkspaceNotFound(PeosError):
    code = "workspace_not_found"
    exit_code = 3


class WorkspaceConfigurationError(PeosError):
    code = "workspace_configuration_error"
    exit_code = 2


class ArtifactNotFound(PeosError):
    code = "artifact_not_found"
    exit_code = 3


class DuplicateArtifactId(PeosError):
    code = "duplicate_artifact_id"
    exit_code = 4


class IntegrityVerificationError(PeosError):
    code = "integrity_verification_error"
    exit_code = 4


class ProjectionUpdateError(PeosError):
    code = "projection_update_failed"
    exit_code = 4


class IndexDirtyError(PeosError):
    code = "index_dirty"
    exit_code = 4


class IndexDivergenceError(PeosError):
    code = "index_divergence"
    exit_code = 4


class IndexRebuildError(PeosError):
    code = "index_rebuild_failed"
    exit_code = 4


class RunNotFound(PeosError):
    code = "run_not_found"
    exit_code = 3


class JournalCorruptionError(PeosError):
    code = "journal_corruption"
    exit_code = 4


class InvalidRunTransition(PeosError):
    code = "invalid_run_transition"
    exit_code = 4


class TerminalRunError(PeosError):
    code = "terminal_run"
    exit_code = 4


class RunConflictError(PeosError):
    code = "run_conflict"
    exit_code = 4


class InputRevisionMismatch(PeosError):
    code = "input_revision_mismatch"
    exit_code = 4


class WorkspaceLockedError(PeosError):
    code = "workspace_locked"
    exit_code = 5
