from __future__ import annotations

import unittest

from arkui_agent.review_service.application import ReviewJobManager
from arkui_agent.review_service.domain import (
    ChangeRef,
    ProviderEvidenceRef,
    ProviderStatus,
    ProviderStatusRef,
    ReviewFailureStage,
    ReviewFinding,
    ReviewIdentity,
    ReviewJobRecord,
    ReviewJobState,
    ReviewRequest,
    ReviewResultSummary,
    ReviewSeverity,
    SourceRange,
)
from arkui_agent.review_service.ports import (
    GitCodeProvider,
    GitCodeProviderError,
    KnowledgeBundle,
    KnowledgeGateway,
    KnowledgeGatewayError,
    ResultStore,
    ResultStoreError,
    ReviewEngine,
    ReviewEngineError,
)
from tests.fixtures.review_service import (
    FakeGitCodeProvider,
    FakeKnowledgeGateway,
    FakeReviewEngine,
    InMemoryResultStore,
)


class ReviewApplicationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        identity = ReviewIdentity(
            repository="arkui/ace_engine",
            pr_id="123",
            head_sha="head123",
            review_policy_version="v1",
        )
        self.request = ReviewRequest(
            identity=identity,
            base_sha="base123",
            diff="@@ -10 +10 @@",
            changed_files=("frameworks/core/example.cpp",),
            changes=(
                ChangeRef(
                    file="frameworks/core/example.cpp",
                    old_range=SourceRange(10, 10),
                    new_range=SourceRange(10, 10),
                ),
            ),
        )
        self.evidence = ProviderEvidenceRef(
            provider="live_source",
            revision="head123",
            source="frameworks/core/example.cpp",
            locator="10",
        )
        self.ready_bundle = KnowledgeBundle(
            evidence=(self.evidence,),
            provider_statuses=(
                ProviderStatusRef(
                    provider="live_source",
                    status=ProviderStatus.READY,
                    revision="head123",
                ),
            ),
        )
        self.finding = ReviewFinding(
            file="frameworks/core/example.cpp",
            location=SourceRange(10, 10),
            category="Stability",
            severity=ReviewSeverity.HIGH,
            title="Guard the callback",
            description="The changed path invokes a nullable callback.",
            evidence=(self.evidence,),
            reasoning="The current source has no guard.",
            suggestion="Check the callback before invoking it.",
            confidence=0.9,
        )

    def manager(
        self,
        gateway: FakeKnowledgeGateway,
        engine: FakeReviewEngine,
        store: InMemoryResultStore,
    ) -> ReviewJobManager:
        return ReviewJobManager(
            knowledge_gateway=gateway,
            review_engine=engine,
            result_store=store,
        )

    def test_test_doubles_satisfy_structural_ports(self) -> None:
        gitcode = FakeGitCodeProvider((self.request,))
        gateway = FakeKnowledgeGateway(self.ready_bundle)
        engine = FakeReviewEngine((self.finding,))
        store = InMemoryResultStore()

        self.assertIsInstance(gitcode, GitCodeProvider)
        self.assertIsInstance(gateway, KnowledgeGateway)
        self.assertIsInstance(engine, ReviewEngine)
        self.assertIsInstance(store, ResultStore)
        self.assertIs(gitcode.load_review(self.request.identity), self.request)
        with self.assertRaisesRegex(GitCodeProviderError, "review request not found"):
            gitcode.load_review(
                ReviewIdentity(
                    repository="arkui/ace_engine",
                    pr_id="missing",
                    head_sha="missing-head",
                    review_policy_version="v1",
                )
            )

    def test_knowledge_bundle_requires_ordered_unique_provider_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "evidence must be a sequence"):
            KnowledgeBundle(
                evidence={self.evidence},
                provider_statuses=self.ready_bundle.provider_statuses,
            )
        with self.assertRaisesRegex(ValueError, "must contain unique provider names"):
            KnowledgeBundle(
                evidence=(self.evidence,),
                provider_statuses=(
                    self.ready_bundle.provider_statuses[0],
                    self.ready_bundle.provider_statuses[0],
                ),
            )

    def test_success_lifecycle_is_deterministic_and_reuses_domain_models(self) -> None:
        gateway = FakeKnowledgeGateway(self.ready_bundle)
        engine = FakeReviewEngine((self.finding,))
        store = InMemoryResultStore()

        record = self.manager(gateway, engine, store).execute(self.request)

        self.assertEqual(
            [item.state for item in store.history],
            [
                ReviewJobState.PENDING,
                ReviewJobState.RUNNING,
                ReviewJobState.SUCCEEDED,
            ],
        )
        self.assertIs(record.request, self.request)
        self.assertEqual(record.findings, (self.finding,))
        self.assertEqual(record.summary.finding_count, 1)
        self.assertFalse(record.summary.degraded)
        self.assertIs(store.get(self.request.identity), record)
        self.assertEqual(gateway.calls, [self.request])
        self.assertEqual(engine.calls, [(self.request, self.ready_bundle)])

    def test_zero_findings_and_stale_optional_provider_succeed_as_degraded(self) -> None:
        bundle = KnowledgeBundle(
            evidence=(self.evidence,),
            provider_statuses=(
                ProviderStatusRef(
                    provider="live_source",
                    status=ProviderStatus.READY,
                    revision="head123",
                ),
                ProviderStatusRef(
                    provider="p2",
                    status=ProviderStatus.STALE,
                    revision="old123",
                ),
            ),
        )
        store = InMemoryResultStore()

        record = self.manager(
            FakeKnowledgeGateway(bundle),
            FakeReviewEngine(()),
            store,
        ).execute(self.request)

        self.assertEqual(record.state, ReviewJobState.SUCCEEDED)
        self.assertEqual(record.findings, ())
        self.assertTrue(record.summary.degraded)
        self.assertEqual(record.summary.finding_count, 0)

    def test_knowledge_failure_is_persisted_as_failed_not_success(self) -> None:
        gateway = FakeKnowledgeGateway(
            self.ready_bundle,
            error=KnowledgeGatewayError("live source unavailable"),
        )
        engine = FakeReviewEngine((self.finding,))
        store = InMemoryResultStore()

        record = self.manager(gateway, engine, store).execute(self.request)

        self.assertEqual(record.state, ReviewJobState.FAILED)
        self.assertEqual(record.failure.stage, ReviewFailureStage.KNOWLEDGE)
        self.assertEqual(record.failure.reason, "live source unavailable")
        self.assertEqual(engine.calls, [])
        self.assertNotIn(ReviewJobState.SUCCEEDED, [item.state for item in store.history])
        self.assertIs(store.get(self.request.identity), record)

    def test_engine_failure_is_persisted_as_failed_not_success(self) -> None:
        store = InMemoryResultStore()
        engine = FakeReviewEngine(
            (),
            error=ReviewEngineError("engine rejected output"),
        )

        record = self.manager(
            FakeKnowledgeGateway(self.ready_bundle),
            engine,
            store,
        ).execute(self.request)

        self.assertEqual(record.state, ReviewJobState.FAILED)
        self.assertEqual(record.failure.stage, ReviewFailureStage.ENGINE)
        self.assertNotIn(ReviewJobState.SUCCEEDED, [item.state for item in store.history])

    def test_store_failure_is_not_hidden_or_rewritten_as_success(self) -> None:
        store = InMemoryResultStore(fail_on_state=ReviewJobState.SUCCEEDED.value)

        with self.assertRaises(ResultStoreError):
            self.manager(
                FakeKnowledgeGateway(self.ready_bundle),
                FakeReviewEngine((self.finding,)),
                store,
            ).execute(self.request)

        self.assertEqual(
            [item.state for item in store.history],
            [ReviewJobState.PENDING, ReviewJobState.RUNNING],
        )

    def test_unexpected_port_exception_is_not_hidden(self) -> None:
        class BrokenGateway:
            def collect(self, request: ReviewRequest) -> KnowledgeBundle:
                raise ValueError("programming error")

        store = InMemoryResultStore()
        manager = ReviewJobManager(
            knowledge_gateway=BrokenGateway(),
            review_engine=FakeReviewEngine(()),
            result_store=store,
        )

        with self.assertRaisesRegex(ValueError, "programming error"):
            manager.execute(self.request)
        self.assertNotIn(ReviewJobState.SUCCEEDED, [item.state for item in store.history])

    def test_job_record_rejects_invalid_success_and_failure_shapes(self) -> None:
        summary = ReviewResultSummary(
            identity=self.request.identity,
            finding_count=0,
            degraded=False,
            provider_statuses=(),
        )
        with self.assertRaisesRegex(ValueError, "finding_count must match"):
            ReviewJobRecord.succeeded(
                self.request,
                findings=(self.finding,),
                summary=summary,
            )
        with self.assertRaisesRegex(ValueError, "require ReviewJobFailure"):
            ReviewJobRecord(request=self.request, state=ReviewJobState.FAILED)
        with self.assertRaisesRegex(ValueError, "findings must be a sequence"):
            ReviewJobRecord.succeeded(
                self.request,
                findings={self.finding},
                summary=ReviewResultSummary(
                    identity=self.request.identity,
                    finding_count=1,
                    degraded=False,
                    provider_statuses=(),
                ),
            )

    def test_expected_port_errors_require_non_empty_reasons(self) -> None:
        for error_type in (
            GitCodeProviderError,
            KnowledgeGatewayError,
            ReviewEngineError,
            ResultStoreError,
        ):
            with self.subTest(error_type=error_type.__name__):
                with self.assertRaisesRegex(ValueError, "reason must be a non-empty"):
                    error_type("  ")


if __name__ == "__main__":
    unittest.main()
