from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain import ReviewIdentity, ReviewJobRecord


@runtime_checkable
class ResultStore(Protocol):
    """Stores the latest state for a normalized review job."""

    def save(self, record: ReviewJobRecord) -> None:
        """Persist the record or raise ResultStoreError."""
        ...

    def get(self, identity: ReviewIdentity) -> ReviewJobRecord | None:
        """Return the latest record for an exact identity."""
        ...
