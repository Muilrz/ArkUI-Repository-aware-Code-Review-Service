"""Pure Code Review domain types and invariants."""

from .agent import AgentReviewRequest
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
from .pull_request import PullRequestContext, PullRequestSummary
from .request import ChangeRef, ReviewRequest
from .result import ReviewResult, ReviewResultStatus, ReviewResultSummary

__all__ = [
    "ChangeRef",
    "AgentReviewRequest",
    "ProviderEvidenceRef",
    "ProviderStatus",
    "ProviderStatusRef",
    "PullRequestContext",
    "PullRequestSummary",
    "ReviewFinding",
    "ReviewFailureStage",
    "ReviewIdentity",
    "ReviewJobFailure",
    "ReviewJobRecord",
    "ReviewJobState",
    "ReviewRequest",
    "ReviewResult",
    "ReviewResultStatus",
    "ReviewResultSummary",
    "ReviewSeverity",
    "SourceRange",
]
