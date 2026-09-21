from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ._validation import non_empty_string
from .pull_request import PullRequestContext


@dataclass(frozen=True, slots=True)
class AgentReviewRequest:
    """Platform-neutral input accepted by any Code Agent backend."""

    repository: str
    pr_id: str
    base_sha: str
    head_sha: str
    changed_files: tuple[str, ...]
    diff: str

    def __post_init__(self) -> None:
        for field in ("repository", "pr_id", "base_sha", "head_sha"):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )
        if isinstance(self.changed_files, (str, bytes)) or not isinstance(
            self.changed_files, Sequence
        ):
            raise ValueError("changed_files must be a sequence of file paths")
        changed_files = tuple(
            non_empty_string(path, field="changed file") for path in self.changed_files
        )
        if not changed_files:
            raise ValueError("changed_files must not be empty")
        if len(changed_files) != len(set(changed_files)):
            raise ValueError("changed_files must contain unique file paths")
        if not isinstance(self.diff, str) or not self.diff.strip():
            raise ValueError("diff must be a non-empty string")
        object.__setattr__(self, "changed_files", changed_files)

    @classmethod
    def from_pull_request(cls, context: PullRequestContext) -> AgentReviewRequest:
        if not isinstance(context, PullRequestContext):
            raise ValueError("context must be PullRequestContext")
        return cls(
            repository=context.repository,
            pr_id=context.pr_id,
            base_sha=context.base_sha,
            head_sha=context.head_sha,
            changed_files=context.changed_files,
            diff=context.diff,
        )
