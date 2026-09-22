from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..domain import (
    AgentKnowledgeContext,
    FastMvpReviewIdentity,
    PullRequestContext,
    PullRequestSummary,
    ReviewResult,
)
from ..domain._validation import non_empty_string


class PollGitCode(Protocol):
    def list_open_prs(self, *, limit: int = 20) -> tuple[PullRequestSummary, ...]: ...
    def get_pr_context(self, pr_id: str | int) -> PullRequestContext: ...
    def post_summary_comment(self, pr_id: str | int, body: str) -> str: ...


class CompletedReviewState(Protocol):
    def has_completed(self, identity: FastMvpReviewIdentity) -> bool: ...
    def record_completed(
        self, identity: FastMvpReviewIdentity, comment_id: str
    ) -> None: ...


class RevisionPreparer(Protocol):
    def prepare(self, head_sha: str) -> AbstractContextManager[Path]: ...


@dataclass(frozen=True, slots=True)
class PollCycleResult:
    discovered: int
    filtered: int
    deduplicated: int
    published: tuple[tuple[FastMvpReviewIdentity, str], ...]


class AutoReviewService:
    """Single-process list → filter → dedup → prepare → review → publish → persist."""

    def __init__(
        self,
        *,
        gitcode: PollGitCode,
        state: CompletedReviewState,
        preparer: RevisionPreparer,
        authors: frozenset[str],
        policy_version: str,
        knowledge_context: Callable[[PullRequestContext, Path], AgentKnowledgeContext],
        review: Callable[[PullRequestContext, AgentKnowledgeContext], ReviewResult],
        publish: Callable[[ReviewResult], str],
    ) -> None:
        if not authors or any(not name.strip() for name in authors):
            raise ValueError("author whitelist must contain at least one user")
        self._gitcode = gitcode
        self._state = state
        self._preparer = preparer
        self._authors = frozenset(authors)
        self._policy_version = non_empty_string(
            policy_version, field="review_policy_version"
        )
        self._knowledge_context = knowledge_context
        self._review = review
        self._publish = publish

    def poll_once(self) -> PollCycleResult:
        summaries = self._gitcode.list_open_prs()
        filtered = deduplicated = 0
        published: list[tuple[FastMvpReviewIdentity, str]] = []
        for summary in summaries:
            if summary.author not in self._authors:
                filtered += 1
                continue
            identity = FastMvpReviewIdentity.from_pr(
                summary, self._policy_version
            )
            if self._state.has_completed(identity):
                deduplicated += 1
                continue
            context = self._gitcode.get_pr_context(summary.pr_id)
            if context.repository != summary.repository or context.pr_id != summary.pr_id:
                raise ValueError("PR detail identity differs from list response")
            if context.author not in self._authors:
                filtered += 1
                continue
            identity = FastMvpReviewIdentity.from_pr(context, self._policy_version)
            if self._state.has_completed(identity):
                deduplicated += 1
                continue
            with self._preparer.prepare(context.head_sha) as prepared_root:
                knowledge = self._knowledge_context(context, prepared_root)
                result = self._review(context, knowledge)
                if (
                    result.repository != context.repository
                    or result.pr_id != context.pr_id
                    or result.base_sha != context.base_sha
                    or result.head_sha != context.head_sha
                ):
                    raise ValueError("review result identity differs from PR context")
                comment_id = self._publish(result)
                self._state.record_completed(identity, comment_id)
                published.append((identity, comment_id))
        return PollCycleResult(len(summaries), filtered, deduplicated, tuple(published))
