"""Pure Code Review domain types and invariants."""

from .evidence import ProviderEvidenceRef, ProviderStatus, ProviderStatusRef
from .finding import ReviewFinding, ReviewSeverity
from .identity import ReviewIdentity
from .job import (
    ReviewFailureStage,
    ReviewJobFailure,
    ReviewJobRecord,
    ReviewJobState,
)
from .location import SourceRange
from .request import ChangeRef, ReviewRequest
from .result import ReviewResultSummary

__all__ = [
    "ChangeRef",
    "ProviderEvidenceRef",
    "ProviderStatus",
    "ProviderStatusRef",
    "ReviewFinding",
    "ReviewFailureStage",
    "ReviewIdentity",
    "ReviewJobFailure",
    "ReviewJobRecord",
    "ReviewJobState",
    "ReviewRequest",
    "ReviewResultSummary",
    "ReviewSeverity",
    "SourceRange",
]
