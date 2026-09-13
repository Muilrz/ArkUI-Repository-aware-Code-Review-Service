from __future__ import annotations

from ..domain._validation import non_empty_string


class ReviewPortError(RuntimeError):
    """Expected failure reported by a Review Service port."""

    def __init__(self, reason: str) -> None:
        super().__init__(non_empty_string(reason, field="reason"))


class GitCodeProviderError(ReviewPortError):
    """The code-host provider could not load a normalized review request."""


class KnowledgeGatewayError(ReviewPortError):
    """The knowledge gateway could not produce evidence for a request."""


class ReviewEngineError(ReviewPortError):
    """The review engine could not evaluate a normalized request."""


class ResultStoreError(ReviewPortError):
    """The result store could not save or retrieve a job record."""
