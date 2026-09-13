from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain import ReviewIdentity, ReviewRequest


@runtime_checkable
class GitCodeProvider(Protocol):
    """Loads a platform-neutral request for an already identified PR revision."""

    def load_review(self, identity: ReviewIdentity) -> ReviewRequest:
        """Return the normalized request or raise GitCodeProviderError."""
        ...
