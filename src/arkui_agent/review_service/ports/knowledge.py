from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain import ReviewRequest
from .models import KnowledgeBundle


@runtime_checkable
class KnowledgeGateway(Protocol):
    """Supplies provider evidence for one normalized review request."""

    def collect(self, request: ReviewRequest) -> KnowledgeBundle:
        """Return evidence/status refs or raise KnowledgeGatewayError."""
        ...
