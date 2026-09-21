from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SummaryCommentPublisher(Protocol):
    """Minimal write boundary for publishing one PR summary comment."""

    def post_summary_comment(self, pr_id: str | int, body: str) -> str:
        """Publish ``body`` and return the platform comment identifier."""
        ...
