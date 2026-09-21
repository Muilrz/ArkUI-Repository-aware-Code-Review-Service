from __future__ import annotations

import unittest
from dataclasses import fields

from arkui_agent.review_service.application import CodeAgentReviewService
from arkui_agent.review_service.domain import (
    AgentReviewRequest,
    PullRequestContext,
    ReviewResult,
    ReviewResultStatus,
)


CONTEXT = PullRequestContext(
    repository="openharmony/arkui_ace_engine",
    pr_id="89521",
    title="fix gesture arbitration",
    author="hct95",
    base_sha="3a1b11c2ec8ead1440f6c71e90f7f8bcb9ecbd1a",
    head_sha="040cac089de659ae2b20e37e4f73c7e27b5281bf",
    changed_files=("frameworks/core/common/event_manager.cpp",),
    diff="@@ -10 +10 @@\n-old\n+new",
)


class RecordingRunner:
    def __init__(self) -> None:
        self.request: AgentReviewRequest | None = None

    def review(self, request: AgentReviewRequest) -> ReviewResult:
        self.request = request
        return ReviewResult(
            status=ReviewResultStatus.SUCCESS,
            repository=request.repository,
            pr_id=request.pr_id,
            base_sha=request.base_sha,
            head_sha=request.head_sha,
            findings=(),
        )


class CodeAgentRunnerTests(unittest.TestCase):
    def test_application_flow_builds_platform_neutral_request(self) -> None:
        runner = RecordingRunner()

        result = CodeAgentReviewService(runner).review(CONTEXT)

        self.assertEqual(result.status, ReviewResultStatus.SUCCESS)
        self.assertEqual(result.findings, ())
        self.assertEqual(
            runner.request,
            AgentReviewRequest(
                repository=CONTEXT.repository,
                pr_id=CONTEXT.pr_id,
                base_sha=CONTEXT.base_sha,
                head_sha=CONTEXT.head_sha,
                changed_files=CONTEXT.changed_files,
                diff=CONTEXT.diff,
            ),
        )

    def test_agent_request_contains_no_backend_specific_fields(self) -> None:
        field_names = {field.name for field in fields(AgentReviewRequest)}

        self.assertEqual(
            field_names,
            {
                "repository",
                "pr_id",
                "base_sha",
                "head_sha",
                "changed_files",
                "diff",
                "knowledge",
            },
        )
        self.assertFalse(any("codex" in name for name in field_names))

    def test_zero_findings_round_trips_as_success(self) -> None:
        result = RecordingRunner().review(AgentReviewRequest.from_pull_request(CONTEXT))

        restored = ReviewResult.from_json(result.to_json())

        self.assertEqual(restored, result)
        self.assertEqual(restored.findings, ())


if __name__ == "__main__":
    unittest.main()
