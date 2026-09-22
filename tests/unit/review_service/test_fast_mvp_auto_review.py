from __future__ import annotations

import tempfile
import sqlite3
from contextlib import closing
import unittest
from pathlib import Path

from arkui_agent.review_service.adapters import SqliteReviewState
from arkui_agent.review_service.application import AutoReviewService
from arkui_agent.review_service.domain import (
    AgentKnowledgeContext,
    FastMvpReviewIdentity,
    ProviderStatus,
    ProviderStatusRef,
    PullRequestContext,
    PullRequestSummary,
    ReviewResult,
    ReviewResultStatus,
)
from arkui_agent.review_service.ports import GitCodeProviderError, ResultStoreError


def context(*, base: str = "base-a", author: str = "allowed") -> PullRequestContext:
    return PullRequestContext(
        repository="owner/repo", pr_id="1", title="change", author=author,
        base_sha=base, head_sha="head-a", changed_files=("a.cpp",),
        diff="@@ -1 +1 @@\n-old\n+new",
    )


def summary(pr: PullRequestContext) -> PullRequestSummary:
    return PullRequestSummary(
        pr.repository, pr.pr_id, pr.title, pr.author, pr.base_sha, pr.head_sha
    )


class FakeGitCode:
    def __init__(self, pr: PullRequestContext) -> None:
        self.pr = pr
        self.events: list[str] = []
        self.fail_publish = False

    def list_open_prs(self, *, limit: int = 20):
        self.events.append("list")
        return (summary(self.pr),)

    def get_pr_context(self, pr_id: str | int):
        self.events.append("detail")
        return self.pr

    def post_summary_comment(self, pr_id: str | int, body: str):
        self.events.append("publish")
        if self.fail_publish:
            raise GitCodeProviderError("failed")
        return "comment-1"


class FakePreparer:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def prepare(self, head_sha: str) -> None:
        self.events.append("prepare")


class AutoReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = SqliteReviewState(Path(self.temp.name) / "state.sqlite")
        self.gitcode = FakeGitCode(context())
        self.events = self.gitcode.events
        self.fail_review = False

    def service(self, *, policy: str = "v1", state=None) -> AutoReviewService:
        def knowledge(pr: PullRequestContext) -> AgentKnowledgeContext:
            self.events.append("knowledge")
            return AgentKnowledgeContext(
                repository_root=self.temp.name,
                skill_path="SKILL.md",
                provider_statuses=(
                    ProviderStatusRef("docs_kb", ProviderStatus.READY, "docs"),
                    ProviderStatusRef("live_source", ProviderStatus.READY, pr.head_sha),
                ),
            )

        def review(pr: PullRequestContext, evidence: AgentKnowledgeContext) -> ReviewResult:
            self.events.append("review")
            if self.fail_review:
                raise RuntimeError("review failed")
            return ReviewResult(
                ReviewResultStatus.SUCCESS, pr.repository, pr.pr_id,
                pr.base_sha, pr.head_sha, (), evidence.degraded,
                evidence.provider_statuses,
            )

        def publish(result: ReviewResult) -> str:
            return self.gitcode.post_summary_comment(result.pr_id, "summary")

        return AutoReviewService(
            gitcode=self.gitcode,
            state=self.state if state is None else state,
            preparer=FakePreparer(self.events),
            authors=frozenset({"allowed"}),
            policy_version=policy,
            knowledge_context=knowledge,
            review=review,
            publish=publish,
        )

    def test_candidate_order_and_successful_persistence(self) -> None:
        cycle = self.service().poll_once()
        self.assertEqual(cycle.discovered, 1)
        self.assertEqual(len(cycle.published), 1)
        self.assertEqual(
            self.events, ["list", "detail", "prepare", "knowledge", "review", "publish"]
        )
        identity, comment_id = cycle.published[0]
        self.assertEqual(comment_id, "comment-1")
        self.assertTrue(self.state.has_completed(identity))

    def test_unlisted_author_never_starts_agent_or_publish(self) -> None:
        self.gitcode.pr = context(author="other")
        cycle = self.service().poll_once()
        self.assertEqual(cycle.filtered, 1)
        self.assertEqual(self.events, ["list"])

    def test_full_identity_dedup_base_change_and_policy_change(self) -> None:
        self.service().poll_once()
        self.events.clear()
        self.assertEqual(self.service().poll_once().deduplicated, 1)
        self.assertEqual(self.events, ["list"])
        self.gitcode.pr = context(base="base-b")
        self.events.clear()
        self.assertEqual(len(self.service().poll_once().published), 1)
        self.events.clear()
        self.assertEqual(len(self.service(policy="v2").poll_once().published), 1)

    def test_failed_review_and_publish_do_not_complete_identity(self) -> None:
        identity = FastMvpReviewIdentity.from_pr(self.gitcode.pr, "v1")
        self.fail_review = True
        with self.assertRaises(RuntimeError):
            self.service().poll_once()
        self.assertFalse(self.state.has_completed(identity))
        self.fail_review = False
        self.gitcode.fail_publish = True
        with self.assertRaises(GitCodeProviderError):
            self.service().poll_once()
        self.assertFalse(self.state.has_completed(identity))

    def test_sqlite_survives_new_instance_and_duplicate_record_fails(self) -> None:
        identity, comment_id = self.service().poll_once().published[0]
        reopened = SqliteReviewState(Path(self.temp.name) / "state.sqlite")
        self.assertTrue(reopened.has_completed(identity))
        with closing(sqlite3.connect(Path(self.temp.name) / "state.sqlite")) as db:
            status, stored_comment, reviewed_at = db.execute(
                "SELECT status, published_comment_id, reviewed_at FROM completed_reviews"
            ).fetchone()
        self.assertEqual(status, "completed")
        self.assertEqual(stored_comment, comment_id)
        self.assertIn("+00:00", reviewed_at)
        with self.assertRaises(ResultStoreError):
            reopened.record_completed(identity, comment_id)

    def test_detail_revision_change_uses_new_identity(self) -> None:
        original = context()

        class ChangedDetailGitCode(FakeGitCode):
            def list_open_prs(self, *, limit: int = 20):
                self.events.append("list")
                return (summary(original),)

        self.gitcode = ChangedDetailGitCode(context(base="base-b"))
        self.events = self.gitcode.events
        cycle = self.service().poll_once()
        self.assertEqual(len(cycle.published), 1)
        self.assertEqual(cycle.published[0][0].base_sha, "base-b")
        self.assertEqual(self.events[0:2], ["list", "detail"])

    def test_persistence_failure_after_publish_is_exposed(self) -> None:
        class FailingState:
            def has_completed(self, identity: FastMvpReviewIdentity) -> bool:
                return False

            def record_completed(
                self, identity: FastMvpReviewIdentity, comment_id: str
            ) -> None:
                raise ResultStoreError("disk write failed")

        service = self.service(state=FailingState())
        with self.assertRaises(ResultStoreError):
            service.poll_once()
        self.assertEqual(self.events[-1], "publish")
