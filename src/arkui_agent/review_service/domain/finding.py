from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ._validation import (
    canonical_json,
    confidence_value,
    load_json_object,
    non_empty_string,
    strict_mapping,
)
from .evidence import ProviderEvidenceRef
from .location import SourceRange


class ReviewSeverity(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    file: str
    location: SourceRange
    category: str
    severity: ReviewSeverity
    title: str
    description: str
    evidence: tuple[ProviderEvidenceRef, ...]
    reasoning: str
    suggestion: str
    confidence: float

    def __post_init__(self) -> None:
        for field in (
            "file",
            "category",
            "title",
            "description",
            "reasoning",
            "suggestion",
        ):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )
        if not isinstance(self.location, SourceRange):
            raise ValueError("location must be SourceRange")
        if not isinstance(self.severity, ReviewSeverity):
            try:
                object.__setattr__(self, "severity", ReviewSeverity(self.severity))
            except (TypeError, ValueError) as error:
                raise ValueError(f"unknown review severity: {self.severity!r}") from error
        if not isinstance(self.evidence, Sequence):
            raise ValueError("evidence must be a sequence of ProviderEvidenceRef")
        evidence = tuple(self.evidence)
        if not evidence or any(
            not isinstance(item, ProviderEvidenceRef) for item in evidence
        ):
            raise ValueError("evidence must contain at least one ProviderEvidenceRef")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "confidence", confidence_value(self.confidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "location": self.location.to_dict(),
            "category": self.category,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "evidence": [item.to_dict() for item in self.evidence],
            "reasoning": self.reasoning,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> ReviewFinding:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset(
                {
                    "file",
                    "location",
                    "category",
                    "severity",
                    "title",
                    "description",
                    "evidence",
                    "reasoning",
                    "suggestion",
                    "confidence",
                }
            ),
        )
        try:
            evidence = tuple(
                ProviderEvidenceRef.from_dict(item) for item in data["evidence"]
            )
        except TypeError as error:
            raise ValueError(
                "evidence must be a sequence of ProviderEvidenceRef objects"
            ) from error
        return cls(
            file=data["file"],
            location=SourceRange.from_dict(data["location"]),
            category=data["category"],
            severity=data["severity"],
            title=data["title"],
            description=data["description"],
            evidence=evidence,
            reasoning=data["reasoning"],
            suggestion=data["suggestion"],
            confidence=data["confidence"],
        )

    @classmethod
    def from_json(cls, payload: str) -> ReviewFinding:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))
