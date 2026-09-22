from __future__ import annotations

from dataclasses import dataclass

from ._validation import non_empty_string
from .pull_request import PullRequestContext, PullRequestSummary


@dataclass(frozen=True, slots=True)
class FastMvpReviewIdentity:
    """M5 dedup key; separate from the frozen R0 ReviewIdentity contract."""

    repository: str
    pr_id: str
    base_sha: str
    head_sha: str
    review_policy_version: str

    def __post_init__(self) -> None:
        for field in (
            "repository", "pr_id", "base_sha", "head_sha", "review_policy_version"
        ):
            object.__setattr__(
                self, field, non_empty_string(getattr(self, field), field=field)
            )

    @classmethod
    def from_pr(
        cls, pr: PullRequestSummary | PullRequestContext, policy_version: str
    ) -> FastMvpReviewIdentity:
        return cls(
            repository=pr.repository,
            pr_id=pr.pr_id,
            base_sha=pr.base_sha,
            head_sha=pr.head_sha,
            review_policy_version=policy_version,
        )
