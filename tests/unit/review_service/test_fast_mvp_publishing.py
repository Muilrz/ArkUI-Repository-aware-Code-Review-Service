from __future__ import annotations

import unittest

from arkui_agent.review_service.application import (
    ReviewPublishingService,
    format_review_summary,
)
from arkui_agent.review_service.domain import (
    ProviderEvidenceRef,
    ProviderStatus,
    ProviderStatusRef,
    ReviewFinding,
    ReviewResult,
    ReviewResultStatus,
    ReviewSeverity,
    SourceRange,
)
from arkui_agent.review_service.ports import GitCodeProviderError


HEAD_SHA = "040cac089de659ae2b20e37e4f73c7e27b5281bf"
BASE_SHA = "3a1b11c2ec8ead1440f6c71e90f7f8bcb9ecbd1a"


def result_with(*findings: ReviewFinding) -> ReviewResult:
    return ReviewResult(
        status=ReviewResultStatus.SUCCESS,
        repository="openharmony/arkui_ace_engine",
        pr_id="89521",
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        findings=findings,
        degraded=True,
        provider_statuses=(
            ProviderStatusRef("docs_kb", ProviderStatus.READY, "sha256:docs"),
            ProviderStatusRef("live_source", ProviderStatus.READY, HEAD_SHA),
            ProviderStatusRef(
                "p1",
                ProviderStatus.UNAVAILABLE,
                diagnostics=("private-token-value",),
            ),
            ProviderStatusRef("p2", ProviderStatus.STALE, "old-revision"),
        ),
    )


def sample_finding() -> ReviewFinding:
    return ReviewFinding(
        file="frameworks/core/common/event_manager.cpp",
        location=SourceRange(42, 44),
        category="Functional Correctness",
        severity=ReviewSeverity.HIGH,
        title="State is committed before validation",
        description="The failure path retains the partially updated state.",
        evidence=(
            ProviderEvidenceRef(
                provider="live_source",
                revision=HEAD_SHA,
                source="frameworks/core/common/event_manager.cpp",
                locator="L42-L44",
            ),
        ),
        reasoning="The next call observes state from a rejected update.",
        suggestion="Validate first, then commit the new state.",
        confidence=0.9,
    )


class RecordingPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    def post_summary_comment(self, pr_id: str | int, body: str) -> str:
        self.calls.append((str(pr_id), body))
        if self.fail:
            raise GitCodeProviderError("comment write failed")
        return "comment-1"


class FastMvpPublishingTests(unittest.TestCase):
    def test_findings_format_includes_required_fields(self) -> None:
        markdown = format_review_summary(result_with(sample_finding()))

        for expected in (
            "[High] State is committed before validation",
            "Category: Functional Correctness",
            "frameworks/core/common/event_manager.cpp:L42-L44",
            "Explanation: The failure path retains the partially updated state.",
            "Evidence: `live_source:",
            "Recommendation: Validate first, then commit the new state.",
        ):
            self.assertIn(expected, markdown)

    def test_zero_findings_is_success_without_overclaiming(self) -> None:
        markdown = format_review_summary(result_with())

        self.assertIn("Review completed successfully", markdown)
        self.assertIn(HEAD_SHA, markdown)
        self.assertIn("No issues with sufficient evidence were found", markdown)
        self.assertIn("does not guarantee that the code is defect-free", markdown)

    def test_degraded_provider_statuses_are_visible_without_diagnostics(self) -> None:
        markdown = format_review_summary(result_with())

        for expected in (
            "degraded: `true`",
            "docs_kb: `ready`",
            "live_source: `ready`",
            "p1: `unavailable`",
            "p2: `stale`",
        ):
            self.assertIn(expected, markdown)
        self.assertNotIn("private-token-value", markdown)

    def test_publish_formats_result_and_returns_comment_id(self) -> None:
        publisher = RecordingPublisher()

        comment_id = ReviewPublishingService(publisher).publish(result_with())

        self.assertEqual(comment_id, "comment-1")
        self.assertEqual(publisher.calls[0][0], "89521")
        self.assertIn("# ArkUI Automated Code Review", publisher.calls[0][1])

    def test_publish_failure_propagates(self) -> None:
        publisher = RecordingPublisher(fail=True)

        with self.assertRaises(GitCodeProviderError):
            ReviewPublishingService(publisher).publish(result_with())


if __name__ == "__main__":
    unittest.main()
