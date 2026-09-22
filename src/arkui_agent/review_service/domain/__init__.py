"""Pure Code Review domain types and invariants."""

from .agent import AgentKnowledgeContext, AgentReviewRequest
from .evidence import ProviderEvidenceRef, ProviderStatus, ProviderStatusRef
from .finding import ReviewFinding, ReviewSeverity
from .fast_mvp_identity import FastMvpReviewIdentity
from .identity import ReviewIdentity
from .job import (
    ReviewFailureStage,
    ReviewJobFailure,
    ReviewJobRecord,
    ReviewJobState,
)
from .knowledge import (
    KnowledgeContext,
    KnowledgeEvidence,
    KnowledgeOperation,
    KnowledgeProviderResult,
    KnowledgeQuery,
)
from .location import SourceRange
from .pull_request import PullRequestContext, PullRequestSummary
from .request import ChangeRef, ReviewRequest
from .result import ReviewResult, ReviewResultStatus, ReviewResultSummary

__all__ = [
    "ChangeRef",
    "AgentReviewRequest",
    "AgentKnowledgeContext",
    "KnowledgeContext",
    "KnowledgeEvidence",
    "KnowledgeOperation",
    "KnowledgeProviderResult",
    "KnowledgeQuery",
    "ProviderEvidenceRef",
    "ProviderStatus",
    "ProviderStatusRef",
    "PullRequestContext",
    "PullRequestSummary",
    "ReviewFinding",
    "FastMvpReviewIdentity",
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
