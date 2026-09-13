from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain import ReviewFinding, ReviewRequest
from .models import KnowledgeBundle


@runtime_checkable
class ReviewEngine(Protocol):
    """Evaluates an R0-B request against provider evidence."""

    def review(
        self,
        request: ReviewRequest,
        knowledge: KnowledgeBundle,
    ) -> tuple[ReviewFinding, ...]:
        """Return structured findings or raise ReviewEngineError."""
        ...
