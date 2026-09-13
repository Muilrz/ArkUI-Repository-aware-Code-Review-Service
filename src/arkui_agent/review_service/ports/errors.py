from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..domain import ReviewFailureStage, ReviewJobFailure
from ..domain._validation import non_empty_string


class ReviewErrorCategory(StrEnum):
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    APPLICATION = "application"
    GITCODE_PROVIDER = "gitcode_provider"
    KNOWLEDGE_GATEWAY = "knowledge_gateway"
    REVIEW_ENGINE = "review_engine"
    RESULT_STORE = "result_store"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class ReviewErrorInfo:
    category: ReviewErrorCategory
    code: str
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.category, ReviewErrorCategory):
            try:
                object.__setattr__(
                    self,
                    "category",
                    ReviewErrorCategory(self.category),
                )
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"unknown review error category: {self.category!r}"
                ) from error
        object.__setattr__(self, "code", non_empty_string(self.code, field="code"))
        object.__setattr__(
            self,
            "message",
            non_empty_string(self.message, field="message"),
        )


class ReviewServiceError(RuntimeError):
    """Expected, classifiable failure within the Review Service boundary."""

    category = ReviewErrorCategory.INTERNAL
    code = "review.internal"
    public_message = "review service failure"

    def __init__(self, reason: str) -> None:
        self.reason = non_empty_string(reason, field="reason")
        super().__init__(self.public_message)

    def __str__(self) -> str:
        return self.public_message

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.public_message!r})"

    def error_info(self) -> ReviewErrorInfo:
        return ReviewErrorInfo(
            category=self.category,
            code=self.code,
            message=self.public_message,
        )


class ReviewConfigurationError(ReviewServiceError):
    category = ReviewErrorCategory.CONFIGURATION
    code = "review.configuration"
    public_message = "review service configuration is invalid"


class ReviewApplicationError(ReviewServiceError):
    category = ReviewErrorCategory.APPLICATION
    code = "review.application"
    public_message = "review application failed"


class ReviewPortError(ReviewServiceError):
    """Expected failure reported by a Review Service port."""

    category = ReviewErrorCategory.APPLICATION
    code = "review.port"
    public_message = "review service port failed"


class GitCodeProviderError(ReviewPortError):
    """The code-host provider could not load a normalized review request."""

    category = ReviewErrorCategory.GITCODE_PROVIDER
    code = "review.port.gitcode"
    public_message = "GitCode provider failed"


class KnowledgeGatewayError(ReviewPortError):
    """The knowledge gateway could not produce evidence for a request."""

    category = ReviewErrorCategory.KNOWLEDGE_GATEWAY
    code = "review.port.knowledge"
    public_message = "knowledge collection failed"


class ReviewEngineError(ReviewPortError):
    """The review engine could not evaluate a normalized request."""

    category = ReviewErrorCategory.REVIEW_ENGINE
    code = "review.port.engine"
    public_message = "review engine failed"


class ResultStoreError(ReviewPortError):
    """The result store could not save or retrieve a job record."""

    category = ReviewErrorCategory.RESULT_STORE
    code = "review.port.result_store"
    public_message = "result store failed"


_JOB_FAILURE_INFO = {
    ReviewFailureStage.KNOWLEDGE: ReviewErrorInfo(
        category=ReviewErrorCategory.KNOWLEDGE_GATEWAY,
        code="review.job.knowledge_failed",
        message="review job failed during knowledge collection",
    ),
    ReviewFailureStage.ENGINE: ReviewErrorInfo(
        category=ReviewErrorCategory.REVIEW_ENGINE,
        code="review.job.engine_failed",
        message="review job failed during review evaluation",
    ),
}


def classify_review_failure(
    failure: BaseException | ReviewJobFailure,
) -> ReviewErrorInfo:
    """Return stable public classification without copying private error detail."""

    if isinstance(failure, ReviewJobFailure):
        return _JOB_FAILURE_INFO[failure.stage]
    if isinstance(failure, ReviewServiceError):
        return failure.error_info()
    if isinstance(failure, ValueError):
        return ReviewErrorInfo(
            category=ReviewErrorCategory.VALIDATION,
            code="review.validation",
            message="review input is invalid",
        )
    if isinstance(failure, BaseException):
        return ReviewErrorInfo(
            category=ReviewErrorCategory.INTERNAL,
            code="review.internal",
            message="unexpected review service failure",
        )
    raise ValueError("failure must be an exception or ReviewJobFailure")
