from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ._validation import (
    canonical_json,
    load_json_object,
    non_empty_string,
    optional_non_empty_string,
    strict_mapping,
    tuple_of_strings,
)


class ProviderStatus(StrEnum):
    READY = "ready"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    REFRESHING = "refreshing"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ProviderEvidenceRef:
    provider: str
    revision: str | None
    source: str
    locator: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider",
            non_empty_string(self.provider, field="provider"),
        )
        object.__setattr__(
            self,
            "revision",
            optional_non_empty_string(self.revision, field="revision"),
        )
        object.__setattr__(
            self,
            "source",
            non_empty_string(self.source, field="source"),
        )
        object.__setattr__(
            self,
            "locator",
            optional_non_empty_string(self.locator, field="locator"),
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "provider": self.provider,
            "revision": self.revision,
            "source": self.source,
            "locator": self.locator,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> ProviderEvidenceRef:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset({"provider", "revision", "source", "locator"}),
        )
        return cls(
            provider=data["provider"],
            revision=data["revision"],
            source=data["source"],
            locator=data["locator"],
        )

    @classmethod
    def from_json(cls, payload: str) -> ProviderEvidenceRef:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))


@dataclass(frozen=True, slots=True)
class ProviderStatusRef:
    provider: str
    status: ProviderStatus
    revision: str | None = None
    version: str | None = None
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider",
            non_empty_string(self.provider, field="provider"),
        )
        if not isinstance(self.status, ProviderStatus):
            try:
                object.__setattr__(self, "status", ProviderStatus(self.status))
            except (TypeError, ValueError) as error:
                raise ValueError(f"unknown provider status: {self.status!r}") from error
        object.__setattr__(
            self,
            "revision",
            optional_non_empty_string(self.revision, field="revision"),
        )
        object.__setattr__(
            self,
            "version",
            optional_non_empty_string(self.version, field="version"),
        )
        object.__setattr__(
            self,
            "diagnostics",
            tuple_of_strings(self.diagnostics, field="diagnostics", allow_empty=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "revision": self.revision,
            "version": self.version,
            "diagnostics": list(self.diagnostics),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> ProviderStatusRef:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset(
                {"provider", "status", "revision", "version", "diagnostics"}
            ),
        )
        return cls(
            provider=data["provider"],
            status=data["status"],
            revision=data["revision"],
            version=data["version"],
            diagnostics=data["diagnostics"],
        )

    @classmethod
    def from_json(cls, payload: str) -> ProviderStatusRef:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))
