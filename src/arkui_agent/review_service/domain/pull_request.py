from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ._validation import non_empty_string


def _pr_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("pr_id must be a positive integer or digit string")
    normalized = str(value).strip()
    if not normalized.isdigit() or int(normalized) <= 0:
        raise ValueError("pr_id must be a positive integer or digit string")
    return normalized


@dataclass(frozen=True, slots=True)
class PullRequestSummary:
    """Platform-neutral GitCode PR metadata used by the Fast-MVP list path."""

    repository: str
    pr_id: str
    title: str
    author: str
    base_sha: str
    head_sha: str

    def __post_init__(self) -> None:
        for field in ("repository", "title", "author", "base_sha", "head_sha"):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )
        object.__setattr__(self, "pr_id", _pr_id(self.pr_id))


@dataclass(frozen=True, slots=True)
class PullRequestContext:
    """Revision-bound PR input before conversion to an R0 ReviewRequest."""

    repository: str
    pr_id: str
    title: str
    author: str
    base_sha: str
    head_sha: str
    changed_files: tuple[str, ...]
    diff: str

    def __post_init__(self) -> None:
        summary = PullRequestSummary(
            repository=self.repository,
            pr_id=self.pr_id,
            title=self.title,
            author=self.author,
            base_sha=self.base_sha,
            head_sha=self.head_sha,
        )
        for field in ("repository", "pr_id", "title", "author", "base_sha", "head_sha"):
            object.__setattr__(self, field, getattr(summary, field))

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
        object.__setattr__(self, "changed_files", changed_files)
        if not isinstance(self.diff, str) or not self.diff.strip():
            raise ValueError("diff must be a non-empty string")
