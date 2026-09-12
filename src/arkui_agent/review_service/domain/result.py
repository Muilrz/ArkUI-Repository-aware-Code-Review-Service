from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ._validation import (
    canonical_json,
    load_json_object,
    non_negative_int,
    strict_mapping,
)
from .evidence import ProviderStatus, ProviderStatusRef
from .identity import ReviewIdentity


@dataclass(frozen=True, slots=True)
class ReviewResultSummary:
    identity: ReviewIdentity
    finding_count: int
    degraded: bool
    provider_statuses: tuple[ProviderStatusRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ReviewIdentity):
            raise ValueError("identity must be ReviewIdentity")
        object.__setattr__(
            self,
            "finding_count",
            non_negative_int(self.finding_count, field="finding_count"),
        )
        if not isinstance(self.degraded, bool):
            raise ValueError("degraded must be a boolean")
        if not isinstance(self.provider_statuses, Sequence):
            raise ValueError(
                "provider_statuses must be a sequence of ProviderStatusRef"
            )
        statuses = tuple(self.provider_statuses)
        if any(not isinstance(status, ProviderStatusRef) for status in statuses):
            raise ValueError(
                "provider_statuses must be a sequence of ProviderStatusRef"
            )
        provider_names = [status.provider for status in statuses]
        if len(provider_names) != len(set(provider_names)):
            raise ValueError("provider_statuses must contain unique provider names")
        if not self.degraded and any(
            status.status is not ProviderStatus.READY for status in statuses
        ):
            raise ValueError("degraded must be true when a provider is not ready")
        object.__setattr__(self, "provider_statuses", statuses)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "finding_count": self.finding_count,
            "degraded": self.degraded,
            "provider_statuses": [
                status.to_dict() for status in self.provider_statuses
            ],
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> ReviewResultSummary:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset(
                {"identity", "finding_count", "degraded", "provider_statuses"}
            ),
        )
        try:
            statuses = tuple(
                ProviderStatusRef.from_dict(item)
                for item in data["provider_statuses"]
            )
        except TypeError as error:
            raise ValueError(
                "provider_statuses must be a sequence of ProviderStatusRef objects"
            ) from error
        return cls(
            identity=ReviewIdentity.from_dict(data["identity"]),
            finding_count=data["finding_count"],
            degraded=data["degraded"],
            provider_statuses=statuses,
        )

    @classmethod
    def from_json(cls, payload: str) -> ReviewResultSummary:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))
