from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeAlias, runtime_checkable

from ..domain import ReviewJobFailure
from ..domain._validation import canonical_json, non_empty_string
from .configuration import SecretValue
from .errors import classify_review_failure


REDACTED = "<redacted>"
DiagnosticScalar: TypeAlias = str | int | float | bool | None
_SENSITIVE_NAMES = (
    "authorization",
    "api_key",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)


def _is_sensitive_name(name: str) -> bool:
    normalized = name.casefold().replace("-", "_").replace(".", "_")
    return any(marker in normalized for marker in _SENSITIVE_NAMES)


class DiagnosticLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ReviewCorrelation:
    """Operational identifiers kept separate from ReviewIdentity."""

    correlation_id: str
    job_id: str

    def __post_init__(self) -> None:
        for field in ("correlation_id", "job_id"):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "correlation_id": self.correlation_id,
            "job_id": self.job_id,
        }


@dataclass(frozen=True, slots=True)
class DiagnosticAttribute:
    name: str
    value: DiagnosticScalar | SecretValue

    def __post_init__(self) -> None:
        name = non_empty_string(self.name, field="diagnostic attribute name")
        value = self.value
        if isinstance(value, SecretValue) or _is_sensitive_name(name):
            value = REDACTED
        elif not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ValueError("diagnostic attribute value must be a scalar")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("diagnostic attribute float must be finite")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "value", value)

    def to_dict(self) -> dict[str, DiagnosticScalar]:
        return {"name": self.name, "value": self.value}


@dataclass(frozen=True, slots=True)
class ReviewDiagnostic:
    correlation: ReviewCorrelation
    level: DiagnosticLevel
    code: str
    message: str
    attributes: tuple[DiagnosticAttribute, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.correlation, ReviewCorrelation):
            raise ValueError("correlation must be ReviewCorrelation")
        if not isinstance(self.level, DiagnosticLevel):
            try:
                object.__setattr__(self, "level", DiagnosticLevel(self.level))
            except (TypeError, ValueError) as error:
                raise ValueError(f"unknown diagnostic level: {self.level!r}") from error
        object.__setattr__(self, "code", non_empty_string(self.code, field="code"))
        object.__setattr__(
            self,
            "message",
            non_empty_string(self.message, field="message"),
        )
        if not isinstance(self.attributes, Sequence):
            raise ValueError("attributes must be a sequence of DiagnosticAttribute")
        attributes = tuple(self.attributes)
        if any(not isinstance(item, DiagnosticAttribute) for item in attributes):
            raise ValueError("attributes must be a sequence of DiagnosticAttribute")
        names = [item.name for item in attributes]
        if len(names) != len(set(names)):
            raise ValueError("attributes must contain unique names")
        object.__setattr__(self, "attributes", attributes)

    @classmethod
    def from_failure(
        cls,
        correlation: ReviewCorrelation,
        failure: BaseException | ReviewJobFailure,
    ) -> ReviewDiagnostic:
        info = classify_review_failure(failure)
        attributes = [
            DiagnosticAttribute("failure_type", type(failure).__name__),
        ]
        if isinstance(failure, ReviewJobFailure):
            attributes.append(
                DiagnosticAttribute("failure_stage", failure.stage.value)
            )
        return cls(
            correlation=correlation,
            level=DiagnosticLevel.ERROR,
            code=info.code,
            message=info.message,
            attributes=tuple(attributes),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "correlation": self.correlation.to_dict(),
            "level": self.level.value,
            "code": self.code,
            "message": self.message,
            "attributes": [item.to_dict() for item in self.attributes],
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@runtime_checkable
class DiagnosticSink(Protocol):
    """Receives structured diagnostics; R0 provides no telemetry backend."""

    def emit(self, diagnostic: ReviewDiagnostic) -> None:
        """Emit one already-redacted diagnostic record."""
        ...
