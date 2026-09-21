from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from ._validation import non_empty_string, optional_non_empty_string
from .evidence import ProviderEvidenceRef, ProviderStatus, ProviderStatusRef


class KnowledgeOperation(StrEnum):
    DOCS_SEARCH = "docs_search"
    LIVE_SEARCH = "live_search"
    LIVE_READ = "live_read"
    P1_LOOKUP = "p1_lookup"
    P2_LOOKUP = "p2_lookup"


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    repository: str
    revision: str
    operation: KnowledgeOperation
    text: str
    path: str | None = None

    def __post_init__(self) -> None:
        for field in ("repository", "revision", "text"):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )
        if not isinstance(self.operation, KnowledgeOperation):
            try:
                object.__setattr__(
                    self, "operation", KnowledgeOperation(self.operation)
                )
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"unknown knowledge operation: {self.operation!r}"
                ) from error
        object.__setattr__(
            self,
            "path",
            optional_non_empty_string(self.path, field="path"),
        )


@dataclass(frozen=True, slots=True)
class KnowledgeEvidence:
    provider: str
    revision: str | None
    source: str
    content: str
    locator: str | None = None

    def __post_init__(self) -> None:
        for field in ("provider", "source", "content"):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )
        object.__setattr__(
            self,
            "revision",
            optional_non_empty_string(self.revision, field="revision"),
        )
        object.__setattr__(
            self,
            "locator",
            optional_non_empty_string(self.locator, field="locator"),
        )

    def to_ref(self) -> ProviderEvidenceRef:
        return ProviderEvidenceRef(
            provider=self.provider,
            revision=self.revision,
            source=self.source,
            locator=self.locator,
        )


@dataclass(frozen=True, slots=True)
class KnowledgeProviderResult:
    status: ProviderStatusRef
    evidence: tuple[KnowledgeEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProviderStatusRef):
            raise ValueError("status must be ProviderStatusRef")
        if not isinstance(self.evidence, Sequence):
            raise ValueError("evidence must be a sequence of KnowledgeEvidence")
        evidence = tuple(self.evidence)
        if any(not isinstance(item, KnowledgeEvidence) for item in evidence):
            raise ValueError("evidence must be a sequence of KnowledgeEvidence")
        if any(item.provider != self.status.provider for item in evidence):
            raise ValueError("evidence provider must match provider status")
        if self.status.status is not ProviderStatus.READY and evidence:
            raise ValueError("non-ready providers must not expose usable evidence")
        object.__setattr__(self, "evidence", evidence)


@dataclass(frozen=True, slots=True)
class KnowledgeContext:
    provider_statuses: tuple[ProviderStatusRef, ...]
    evidence: tuple[KnowledgeEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.provider_statuses, Sequence):
            raise ValueError("provider_statuses must be a sequence")
        statuses = tuple(self.provider_statuses)
        if any(not isinstance(item, ProviderStatusRef) for item in statuses):
            raise ValueError("provider_statuses must contain ProviderStatusRef")
        names = [item.provider for item in statuses]
        if len(names) != len(set(names)):
            raise ValueError("provider_statuses must contain unique providers")
        if not isinstance(self.evidence, Sequence):
            raise ValueError("evidence must be a sequence")
        evidence = tuple(self.evidence)
        if any(not isinstance(item, KnowledgeEvidence) for item in evidence):
            raise ValueError("evidence must contain KnowledgeEvidence")
        ready = {
            item.provider
            for item in statuses
            if item.status is ProviderStatus.READY
        }
        if any(item.provider not in ready for item in evidence):
            raise ValueError("evidence may only come from ready providers")
        object.__setattr__(self, "provider_statuses", statuses)
        object.__setattr__(self, "evidence", evidence)

    @property
    def degraded(self) -> bool:
        return any(
            status.status is not ProviderStatus.READY
            for status in self.provider_statuses
        )

