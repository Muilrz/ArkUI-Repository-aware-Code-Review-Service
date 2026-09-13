from __future__ import annotations

from collections.abc import Sequence

from arkui_agent.review_service.domain import (
    ReviewFinding,
    ReviewIdentity,
    ReviewJobRecord,
    ReviewRequest,
)
from arkui_agent.review_service.ports import (
    GitCodeProviderError,
    KnowledgeBundle,
    KnowledgeGatewayError,
    ResultStoreError,
    ReviewEngineError,
)


class FakeGitCodeProvider:
    def __init__(self, requests: Sequence[ReviewRequest]) -> None:
        self._requests = {request.identity: request for request in requests}
        self.calls: list[ReviewIdentity] = []

    def load_review(self, identity: ReviewIdentity) -> ReviewRequest:
        self.calls.append(identity)
        try:
            return self._requests[identity]
        except KeyError as error:
            raise GitCodeProviderError(f"review request not found: {identity}") from error


class FakeKnowledgeGateway:
    def __init__(
        self,
        bundle: KnowledgeBundle,
        *,
        error: KnowledgeGatewayError | None = None,
    ) -> None:
        self._bundle = bundle
        self._error = error
        self.calls: list[ReviewRequest] = []

    def collect(self, request: ReviewRequest) -> KnowledgeBundle:
        self.calls.append(request)
        if self._error is not None:
            raise self._error
        return self._bundle


class FakeReviewEngine:
    def __init__(
        self,
        findings: Sequence[ReviewFinding],
        *,
        error: ReviewEngineError | None = None,
    ) -> None:
        self._findings = tuple(findings)
        self._error = error
        self.calls: list[tuple[ReviewRequest, KnowledgeBundle]] = []

    def review(
        self,
        request: ReviewRequest,
        knowledge: KnowledgeBundle,
    ) -> tuple[ReviewFinding, ...]:
        self.calls.append((request, knowledge))
        if self._error is not None:
            raise self._error
        return self._findings


class InMemoryResultStore:
    def __init__(self, *, fail_on_state: str | None = None) -> None:
        self._latest: dict[ReviewIdentity, ReviewJobRecord] = {}
        self.fail_on_state = fail_on_state
        self.history: list[ReviewJobRecord] = []

    def save(self, record: ReviewJobRecord) -> None:
        if record.state.value == self.fail_on_state:
            raise ResultStoreError(f"store rejected {record.state.value}")
        self._latest[record.identity] = record
        self.history.append(record)

    def get(self, identity: ReviewIdentity) -> ReviewJobRecord | None:
        return self._latest.get(identity)
