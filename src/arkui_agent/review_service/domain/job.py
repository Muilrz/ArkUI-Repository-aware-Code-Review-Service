from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from ._validation import non_empty_string
from .finding import ReviewFinding
from .identity import ReviewIdentity
from .request import ReviewRequest
from .result import ReviewResultSummary


class ReviewJobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ReviewFailureStage(StrEnum):
    KNOWLEDGE = "knowledge"
    ENGINE = "engine"


@dataclass(frozen=True, slots=True)
class ReviewJobFailure:
    stage: ReviewFailureStage
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage, ReviewFailureStage):
            try:
                object.__setattr__(self, "stage", ReviewFailureStage(self.stage))
            except (TypeError, ValueError) as error:
                raise ValueError(f"unknown review failure stage: {self.stage!r}") from error
        object.__setattr__(
            self,
            "reason",
            non_empty_string(self.reason, field="reason"),
        )


@dataclass(frozen=True, slots=True)
class ReviewJobRecord:
    request: ReviewRequest
    state: ReviewJobState
    findings: tuple[ReviewFinding, ...] = ()
    summary: ReviewResultSummary | None = None
    failure: ReviewJobFailure | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, ReviewRequest):
            raise ValueError("request must be ReviewRequest")
        if not isinstance(self.state, ReviewJobState):
            try:
                object.__setattr__(self, "state", ReviewJobState(self.state))
            except (TypeError, ValueError) as error:
                raise ValueError(f"unknown review job state: {self.state!r}") from error
        if not isinstance(self.findings, Sequence):
            raise ValueError("findings must be a sequence of ReviewFinding")
        findings = tuple(self.findings)
        if any(not isinstance(finding, ReviewFinding) for finding in findings):
            raise ValueError("findings must be a sequence of ReviewFinding")
        object.__setattr__(self, "findings", findings)

        if self.state in {ReviewJobState.PENDING, ReviewJobState.RUNNING}:
            if findings or self.summary is not None or self.failure is not None:
                raise ValueError(
                    f"{self.state.value} jobs cannot contain findings, summary, or failure"
                )
            return
        if self.state is ReviewJobState.SUCCEEDED:
            self._validate_succeeded(findings)
            return
        self._validate_failed(findings)

    @property
    def identity(self) -> ReviewIdentity:
        return self.request.identity

    def _validate_succeeded(self, findings: tuple[ReviewFinding, ...]) -> None:
        if not isinstance(self.summary, ReviewResultSummary):
            raise ValueError("succeeded jobs require ReviewResultSummary")
        if self.failure is not None:
            raise ValueError("succeeded jobs cannot contain failure")
        if self.summary.identity != self.identity:
            raise ValueError("summary identity must match request identity")
        if self.summary.finding_count != len(findings):
            raise ValueError("summary finding_count must match findings")

    def _validate_failed(self, findings: tuple[ReviewFinding, ...]) -> None:
        if findings or self.summary is not None:
            raise ValueError("failed jobs cannot contain findings or summary")
        if not isinstance(self.failure, ReviewJobFailure):
            raise ValueError("failed jobs require ReviewJobFailure")

    @classmethod
    def pending(cls, request: ReviewRequest) -> ReviewJobRecord:
        return cls(request=request, state=ReviewJobState.PENDING)

    @classmethod
    def running(cls, request: ReviewRequest) -> ReviewJobRecord:
        return cls(request=request, state=ReviewJobState.RUNNING)

    @classmethod
    def succeeded(
        cls,
        request: ReviewRequest,
        *,
        findings: Sequence[ReviewFinding],
        summary: ReviewResultSummary,
    ) -> ReviewJobRecord:
        if not isinstance(findings, Sequence):
            raise ValueError("findings must be a sequence of ReviewFinding")
        return cls(
            request=request,
            state=ReviewJobState.SUCCEEDED,
            findings=tuple(findings),
            summary=summary,
        )

    @classmethod
    def failed(
        cls,
        request: ReviewRequest,
        *,
        failure: ReviewJobFailure,
    ) -> ReviewJobRecord:
        return cls(
            request=request,
            state=ReviewJobState.FAILED,
            failure=failure,
        )
