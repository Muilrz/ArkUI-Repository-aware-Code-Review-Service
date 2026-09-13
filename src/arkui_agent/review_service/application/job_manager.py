from __future__ import annotations

from ..domain import (
    ProviderStatus,
    ReviewFailureStage,
    ReviewJobFailure,
    ReviewJobRecord,
    ReviewRequest,
    ReviewResultSummary,
)
from ..ports import (
    KnowledgeGateway,
    KnowledgeGatewayError,
    ResultStore,
    ReviewEngine,
    ReviewEngineError,
)


class ReviewJobManager:
    """Runs one normalized request through the R0-C synchronous lifecycle."""

    def __init__(
        self,
        *,
        knowledge_gateway: KnowledgeGateway,
        review_engine: ReviewEngine,
        result_store: ResultStore,
    ) -> None:
        self._knowledge_gateway = knowledge_gateway
        self._review_engine = review_engine
        self._result_store = result_store

    def execute(self, request: ReviewRequest) -> ReviewJobRecord:
        if not isinstance(request, ReviewRequest):
            raise ValueError("request must be ReviewRequest")

        self._result_store.save(ReviewJobRecord.pending(request))
        self._result_store.save(ReviewJobRecord.running(request))

        try:
            knowledge = self._knowledge_gateway.collect(request)
        except KnowledgeGatewayError as error:
            return self._save_failure(
                request,
                stage=ReviewFailureStage.KNOWLEDGE,
                reason=str(error),
            )

        try:
            findings = self._review_engine.review(request, knowledge)
        except ReviewEngineError as error:
            return self._save_failure(
                request,
                stage=ReviewFailureStage.ENGINE,
                reason=str(error),
            )

        summary = ReviewResultSummary(
            identity=request.identity,
            finding_count=len(findings),
            degraded=any(
                status.status is not ProviderStatus.READY
                for status in knowledge.provider_statuses
            ),
            provider_statuses=knowledge.provider_statuses,
        )
        succeeded = ReviewJobRecord.succeeded(
            request,
            findings=findings,
            summary=summary,
        )
        self._result_store.save(succeeded)
        return succeeded

    def _save_failure(
        self,
        request: ReviewRequest,
        *,
        stage: ReviewFailureStage,
        reason: str,
    ) -> ReviewJobRecord:
        failed = ReviewJobRecord.failed(
            request,
            failure=ReviewJobFailure(stage=stage, reason=reason),
        )
        self._result_store.save(failed)
        return failed
