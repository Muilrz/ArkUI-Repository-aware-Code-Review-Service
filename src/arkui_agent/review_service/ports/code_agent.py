from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain import AgentReviewRequest, ReviewResult


@runtime_checkable
class CodeAgentRunner(Protocol):
    """Runs one platform-neutral review request through a selected backend."""

    def review(self, request: AgentReviewRequest) -> ReviewResult:
        """Return validated success, or raise CodeAgentError on any failure."""
        ...
