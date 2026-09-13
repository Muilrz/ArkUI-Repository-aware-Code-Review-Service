from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..domain._validation import non_empty_string


class SecretValue:
    """Opaque secret whose ordinary display is always redacted.

    ``reveal`` is an explicit adapter-boundary operation. Callers must never put
    its return value in exceptions, diagnostics, logs, or review results.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("secret value must be a non-empty string")
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"


@dataclass(frozen=True, slots=True)
class ReviewServiceConfig:
    """Public, non-secret configuration shared by Review Service adapters."""

    review_policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "review_policy_version",
            non_empty_string(
                self.review_policy_version,
                field="review_policy_version",
            ),
        )


@runtime_checkable
class ReviewConfigurationSource(Protocol):
    """Loads public configuration and resolves secrets through separate paths."""

    def load_service_config(self) -> ReviewServiceConfig:
        """Return validated non-secret service configuration."""
        ...

    def get_secret(self, name: str) -> SecretValue | None:
        """Return an opaque secret, without exposing its value in public config."""
        ...
