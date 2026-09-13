from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..domain import ProviderEvidenceRef, ProviderStatusRef


@dataclass(frozen=True, slots=True)
class KnowledgeBundle:
    """Minimal R0-C carrier between the knowledge and engine ports.

    This is not the ranked and budgeted ReviewContextPack planned for R3.
    """

    evidence: tuple[ProviderEvidenceRef, ...]
    provider_statuses: tuple[ProviderStatusRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, Sequence):
            raise ValueError("evidence must be a sequence of ProviderEvidenceRef")
        evidence = tuple(self.evidence)
        if any(not isinstance(item, ProviderEvidenceRef) for item in evidence):
            raise ValueError("evidence must be a sequence of ProviderEvidenceRef")
        if not isinstance(self.provider_statuses, Sequence):
            raise ValueError(
                "provider_statuses must be a sequence of ProviderStatusRef"
            )
        statuses = tuple(self.provider_statuses)
        if any(not isinstance(item, ProviderStatusRef) for item in statuses):
            raise ValueError(
                "provider_statuses must be a sequence of ProviderStatusRef"
            )
        providers = [status.provider for status in statuses]
        if len(providers) != len(set(providers)):
            raise ValueError("provider_statuses must contain unique provider names")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "provider_statuses", statuses)
