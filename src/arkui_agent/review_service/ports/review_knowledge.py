from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain import KnowledgeProviderResult, KnowledgeQuery


@runtime_checkable
class ReviewKnowledgeProvider(Protocol):
    name: str

    def probe(self, repository: str, revision: str) -> KnowledgeProviderResult:
        """Report availability and freshness without fabricating evidence."""
        ...

    def query(self, query: KnowledgeQuery) -> KnowledgeProviderResult:
        """Return provider-labelled evidence or an explicit non-ready status."""
        ...

