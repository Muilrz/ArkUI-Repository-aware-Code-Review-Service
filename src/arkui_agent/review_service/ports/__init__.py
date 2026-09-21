"""Abstract boundaries required by the Code Review application layer."""

from .configuration import (
    ReviewConfigurationSource,
    ReviewServiceConfig,
    SecretValue,
)
from .code_agent import CodeAgentRunner
from .diagnostics import (
    DiagnosticAttribute,
    DiagnosticLevel,
    DiagnosticSink,
    ReviewCorrelation,
    ReviewDiagnostic,
)
from .engine import ReviewEngine
from .errors import (
    CodeAgentError,
    GitCodeProviderError,
    KnowledgeGatewayError,
    ResultStoreError,
    ReviewApplicationError,
    ReviewConfigurationError,
    ReviewEngineError,
    ReviewErrorCategory,
    ReviewErrorInfo,
    ReviewPortError,
    ReviewServiceError,
    classify_review_failure,
)
from .gitcode import GitCodeProvider
from .knowledge import KnowledgeGateway
from .models import KnowledgeBundle
from .publishing import SummaryCommentPublisher
from .result_store import ResultStore
from .review_knowledge import ReviewKnowledgeProvider

__all__ = [
    "CodeAgentError",
    "CodeAgentRunner",
    "DiagnosticAttribute",
    "DiagnosticLevel",
    "DiagnosticSink",
    "GitCodeProvider",
    "GitCodeProviderError",
    "KnowledgeBundle",
    "KnowledgeGateway",
    "KnowledgeGatewayError",
    "ResultStore",
    "ResultStoreError",
    "ReviewApplicationError",
    "ReviewConfigurationError",
    "ReviewConfigurationSource",
    "ReviewCorrelation",
    "ReviewDiagnostic",
    "ReviewEngine",
    "ReviewEngineError",
    "ReviewErrorCategory",
    "ReviewErrorInfo",
    "ReviewPortError",
    "ReviewKnowledgeProvider",
    "ReviewServiceConfig",
    "ReviewServiceError",
    "SecretValue",
    "SummaryCommentPublisher",
    "classify_review_failure",
]
