from __future__ import annotations

from collections.abc import Mapping

from ..domain import (
    KnowledgeContext,
    KnowledgeOperation,
    KnowledgeProviderResult,
    KnowledgeQuery,
    ProviderStatus,
)
from ..ports import KnowledgeGatewayError, ReviewKnowledgeProvider


class ReviewKnowledgeFacade:
    """Thin provider facade for service callers and tool-capable agents."""

    def __init__(self, providers: Mapping[str, ReviewKnowledgeProvider]) -> None:
        required = {"docs_kb", "live_source"}
        allowed = required | {"p1", "p2"}
        if not required <= set(providers) <= allowed:
            raise ValueError(
                "providers must contain docs_kb and live_source, with optional p1 and p2"
            )
        if any(provider.name != name for name, provider in providers.items()):
            raise ValueError("provider mapping key must match provider name")
        self._providers = dict(providers)

    def prepare(
        self,
        *,
        repository: str,
        revision: str,
        docs_query: str,
    ) -> KnowledgeContext:
        live = self._providers["live_source"].probe(repository, revision)
        if live.status.status is not ProviderStatus.READY:
            raise KnowledgeGatewayError(
                "Live Source is not aligned to the requested revision"
            )

        docs = self._providers["docs_kb"].query(
            KnowledgeQuery(
                repository=repository,
                revision=revision,
                operation=KnowledgeOperation.DOCS_SEARCH,
                text=docs_query,
            )
        )
        results = (docs, live) + tuple(
            self._providers[name].probe(repository, revision)
            for name in ("p1", "p2")
            if name in self._providers
        )
        return KnowledgeContext(
            provider_statuses=tuple(result.status for result in results),
            evidence=tuple(
                evidence for result in results for evidence in result.evidence
            ),
        )

    def query(
        self, provider: str, query: KnowledgeQuery
    ) -> KnowledgeProviderResult:
        try:
            selected = self._providers[provider]
        except KeyError as error:
            raise ValueError(f"unknown knowledge provider: {provider}") from error
        return selected.query(query)
