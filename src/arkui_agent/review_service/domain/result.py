from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ._validation import (
    canonical_json,
    load_json_object,
    non_empty_string,
    non_negative_int,
    strict_mapping,
)
from .evidence import ProviderStatus, ProviderStatusRef
from .finding import ReviewFinding
from .identity import ReviewIdentity


class ReviewResultStatus(StrEnum):
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """Successful platform-neutral result returned by a Code Agent backend.

    Invocation and validation failures are represented by typed exceptions, never
    by an empty findings collection.
    """

    status: ReviewResultStatus
    repository: str
    pr_id: str
    base_sha: str
    head_sha: str
    findings: tuple[ReviewFinding, ...]
    degraded: bool = False
    provider_statuses: tuple[ProviderStatusRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReviewResultStatus):
            try:
                object.__setattr__(self, "status", ReviewResultStatus(self.status))
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"unknown review result status: {self.status!r}"
                ) from error
        for field in ("repository", "pr_id", "base_sha", "head_sha"):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )
        if not isinstance(self.findings, Sequence):
            raise ValueError("findings must be a sequence of ReviewFinding")
        findings = tuple(self.findings)
        if any(not isinstance(finding, ReviewFinding) for finding in findings):
            raise ValueError("findings must be a sequence of ReviewFinding")
        object.__setattr__(self, "findings", findings)
        if not isinstance(self.degraded, bool):
            raise ValueError("degraded must be a boolean")
        if not isinstance(self.provider_statuses, Sequence):
            raise ValueError("provider_statuses must be a sequence")
        statuses = tuple(self.provider_statuses)
        if any(not isinstance(item, ProviderStatusRef) for item in statuses):
            raise ValueError("provider_statuses must contain ProviderStatusRef")
        names = [item.provider for item in statuses]
        if len(names) != len(set(names)):
            raise ValueError("provider_statuses must contain unique providers")
        has_non_ready = any(
            item.status is not ProviderStatus.READY for item in statuses
        )
        if has_non_ready and not self.degraded:
            raise ValueError("degraded must be true when a provider is not ready")
        object.__setattr__(self, "provider_statuses", statuses)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "repository": self.repository,
            "pr_id": self.pr_id,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "findings": [finding.to_dict() for finding in self.findings],
            "degraded": self.degraded,
            "provider_statuses": [
                status.to_dict() for status in self.provider_statuses
            ],
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> ReviewResult:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset(
                {
                    "status",
                    "repository",
                    "pr_id",
                    "base_sha",
                    "head_sha",
                    "findings",
                    "degraded",
                    "provider_statuses",
                }
            ),
        )
        raw_findings = data["findings"]
        if isinstance(raw_findings, (str, bytes)) or not isinstance(
            raw_findings, Sequence
        ):
            raise ValueError("findings must be a sequence of ReviewFinding")
        try:
            findings = tuple(ReviewFinding.from_dict(item) for item in raw_findings)
        except TypeError as error:
            raise ValueError("findings must be a sequence of ReviewFinding") from error
        raw_statuses = data["provider_statuses"]
        if isinstance(raw_statuses, (str, bytes)) or not isinstance(
            raw_statuses, Sequence
        ):
            raise ValueError("provider_statuses must be a sequence")
        statuses = tuple(ProviderStatusRef.from_dict(item) for item in raw_statuses)
        return cls(
            status=data["status"],
            repository=data["repository"],
            pr_id=data["pr_id"],
            base_sha=data["base_sha"],
            head_sha=data["head_sha"],
            findings=findings,
            degraded=data["degraded"],
            provider_statuses=statuses,
        )

    @classmethod
    def from_json(cls, payload: str) -> ReviewResult:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))


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
