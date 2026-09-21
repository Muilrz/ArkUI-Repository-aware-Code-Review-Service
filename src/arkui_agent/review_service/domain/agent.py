from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ._validation import non_empty_string
from .evidence import ProviderStatus, ProviderStatusRef
from .knowledge import KnowledgeEvidence
from .pull_request import PullRequestContext


@dataclass(frozen=True, slots=True)
class AgentKnowledgeContext:
    """Backend-neutral access information for repository-aware review."""

    repository_root: str
    skill_path: str
    provider_statuses: tuple[ProviderStatusRef, ...]
    initial_evidence: tuple[KnowledgeEvidence, ...] = ()

    def __post_init__(self) -> None:
        for field in ("repository_root", "skill_path"):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )
        if isinstance(self.provider_statuses, (str, bytes)) or not isinstance(
            self.provider_statuses, Sequence
        ):
            raise ValueError("provider_statuses must be a sequence")
        statuses = tuple(self.provider_statuses)
        if any(not isinstance(item, ProviderStatusRef) for item in statuses):
            raise ValueError("provider_statuses must contain ProviderStatusRef")
        names = [item.provider for item in statuses]
        if len(names) != len(set(names)):
            raise ValueError("provider_statuses must contain unique providers")
        if {"docs_kb", "live_source"} - set(names):
            raise ValueError("Docs KB and Live Source statuses are required")
        live = next(item for item in statuses if item.provider == "live_source")
        if live.status is not ProviderStatus.READY:
            raise ValueError("Live Source must be ready before Agent invocation")
        if isinstance(self.initial_evidence, (str, bytes)) or not isinstance(
            self.initial_evidence, Sequence
        ):
            raise ValueError("initial_evidence must be a sequence")
        evidence = tuple(self.initial_evidence)
        if any(not isinstance(item, KnowledgeEvidence) for item in evidence):
            raise ValueError("initial_evidence must contain KnowledgeEvidence")
        object.__setattr__(self, "provider_statuses", statuses)
        object.__setattr__(self, "initial_evidence", evidence)

    @property
    def degraded(self) -> bool:
        return any(
            item.status is not ProviderStatus.READY
            for item in self.provider_statuses
        )


@dataclass(frozen=True, slots=True)
class AgentReviewRequest:
    """Platform-neutral input accepted by any Code Agent backend."""

    repository: str
    pr_id: str
    base_sha: str
    head_sha: str
    changed_files: tuple[str, ...]
    diff: str
    knowledge: AgentKnowledgeContext | None = None

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
        if self.knowledge is not None:
            if not isinstance(self.knowledge, AgentKnowledgeContext):
                raise ValueError("knowledge must be AgentKnowledgeContext")
            live = next(
                item
                for item in self.knowledge.provider_statuses
                if item.provider == "live_source"
            )
            if live.revision != self.head_sha:
                raise ValueError("Live Source revision must match head_sha")
        object.__setattr__(self, "changed_files", changed_files)

    @classmethod
    def from_pull_request(
        cls,
        context: PullRequestContext,
        *,
        knowledge: AgentKnowledgeContext | None = None,
    ) -> AgentReviewRequest:
        if not isinstance(context, PullRequestContext):
            raise ValueError("context must be PullRequestContext")
        return cls(
            repository=context.repository,
            pr_id=context.pr_id,
            base_sha=context.base_sha,
            head_sha=context.head_sha,
            changed_files=context.changed_files,
            diff=context.diff,
            knowledge=knowledge,
        )
