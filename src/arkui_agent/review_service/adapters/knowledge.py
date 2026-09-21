from __future__ import annotations

import hashlib
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from ..domain import (
    KnowledgeEvidence,
    KnowledgeOperation,
    KnowledgeProviderResult,
    KnowledgeQuery,
    ProviderStatus,
    ProviderStatusRef,
)
from .process import ProcessResult, ProcessRunner, SubprocessRunner


KnowledgeQueryHandler = Callable[
    [KnowledgeQuery], Sequence[KnowledgeEvidence]
]


class DocsKbProvider:
    name = "docs_kb"

    def __init__(
        self,
        repository_root: Path,
        *,
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self._root = repository_root.resolve()
        self._runner = process_runner or SubprocessRunner()

    def probe(self, repository: str, revision: str) -> KnowledgeProviderResult:
        del repository, revision
        script = self._root / "docs" / "kb_search.py"
        registry = self._root / "docs" / "context_registry.json"
        if not script.is_file() or not registry.is_file():
            return _result(
                self.name,
                ProviderStatus.UNAVAILABLE,
                diagnostics=("docs/kb_search.py or context_registry.json is unavailable",),
            )
        try:
            revision_value = _file_revision(registry)
        except OSError as error:
            return _result(
                self.name,
                ProviderStatus.ERROR,
                diagnostics=(f"Docs KB revision failed: {type(error).__name__}",),
            )
        return _result(
            self.name, ProviderStatus.READY, revision=revision_value
        )

    def query(self, query: KnowledgeQuery) -> KnowledgeProviderResult:
        if query.operation is not KnowledgeOperation.DOCS_SEARCH:
            raise ValueError("DocsKbProvider only supports docs_search")
        status = self.probe(query.repository, query.revision).status
        if status.status is not ProviderStatus.READY:
            return KnowledgeProviderResult(status=status)
        try:
            completed = self._runner.run(
                (
                    sys.executable,
                    "docs/kb_search.py",
                    query.text,
                    "--detail",
                ),
                stdin="",
                cwd=self._root,
                timeout_seconds=30,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=status.revision,
                diagnostics=(f"kb_search failed: {type(error).__name__}",),
            )
        if completed.exit_code != 0:
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=status.revision,
                diagnostics=(
                    f"kb_search exited with code {completed.exit_code}",
                ),
            )
        output = completed.stdout.strip()
        evidence = ()
        if output:
            evidence = (
                KnowledgeEvidence(
                    provider=self.name,
                    revision=status.revision,
                    source="docs/context_registry.json",
                    locator=f"kb_search --detail {query.text}",
                    content=output,
                ),
            )
        return KnowledgeProviderResult(status=status, evidence=evidence)


class LiveSourceProvider:
    name = "live_source"

    def __init__(
        self,
        repository_root: Path,
        *,
        process_runner: ProcessRunner | None = None,
        max_output_chars: int = 20_000,
    ) -> None:
        self._root = repository_root.resolve()
        self._runner = process_runner or SubprocessRunner()
        if max_output_chars < 1:
            raise ValueError("max_output_chars must be positive")
        self._max_output_chars = max_output_chars

    @property
    def repository_root(self) -> Path:
        return self._root

    def probe(self, repository: str, revision: str) -> KnowledgeProviderResult:
        del repository
        try:
            head = self._run(("git", "rev-parse", "HEAD"))
        except (OSError, subprocess.TimeoutExpired) as error:
            return _result(
                self.name,
                ProviderStatus.UNAVAILABLE,
                diagnostics=(f"Git probe failed: {type(error).__name__}",),
            )
        if head.exit_code != 0 or not head.stdout.strip():
            return _result(
                self.name,
                ProviderStatus.UNAVAILABLE,
                diagnostics=("target path is not a readable Git worktree",),
            )
        actual = head.stdout.strip()
        if actual != revision:
            return _result(
                self.name,
                ProviderStatus.STALE,
                revision=actual,
                diagnostics=("target worktree HEAD does not match review revision",),
            )
        try:
            status = self._run(
                ("git", "status", "--porcelain", "--untracked-files=no")
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=actual,
                diagnostics=(f"Git status failed: {type(error).__name__}",),
            )
        if status.exit_code != 0:
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=actual,
                diagnostics=("target worktree status could not be verified",),
            )
        if status.stdout.strip():
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=actual,
                diagnostics=("target worktree has tracked source modifications",),
            )
        return _result(self.name, ProviderStatus.READY, revision=actual)

    def query(self, query: KnowledgeQuery) -> KnowledgeProviderResult:
        status = self.probe(query.repository, query.revision).status
        if status.status is not ProviderStatus.READY:
            return KnowledgeProviderResult(status=status)
        if query.operation is KnowledgeOperation.LIVE_SEARCH:
            return self._search(query, status)
        if query.operation is KnowledgeOperation.LIVE_READ:
            return self._read(query, status)
        raise ValueError("LiveSourceProvider supports live_search and live_read")

    def _search(
        self, query: KnowledgeQuery, status: ProviderStatusRef
    ) -> KnowledgeProviderResult:
        command = [
            "rg",
            "--line-number",
            "--column",
            "--fixed-strings",
            "--max-count",
            "20",
            "--",
            query.text,
        ]
        if query.path is not None:
            command.append(query.path)
        try:
            completed = self._run(tuple(command))
        except (OSError, subprocess.TimeoutExpired) as error:
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=status.revision,
                diagnostics=(f"Live search failed: {type(error).__name__}",),
            )
        if completed.exit_code not in (0, 1):
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=status.revision,
                diagnostics=(f"rg exited with code {completed.exit_code}",),
            )
        output = completed.stdout[: self._max_output_chars].strip()
        evidence = ()
        if output:
            evidence = (
                KnowledgeEvidence(
                    provider=self.name,
                    revision=status.revision,
                    source=query.path or ".",
                    locator=f"rg --fixed-strings {query.text}",
                    content=output,
                ),
            )
        return KnowledgeProviderResult(status=status, evidence=evidence)

    def _read(
        self, query: KnowledgeQuery, status: ProviderStatusRef
    ) -> KnowledgeProviderResult:
        if query.path is None:
            raise ValueError("live_read requires a repository-relative path")
        path = _safe_repository_path(self._root, query.path)
        if not path.is_file():
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=status.revision,
                diagnostics=("requested source file is unavailable",),
            )
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=status.revision,
                diagnostics=(f"Live read failed: {type(error).__name__}",),
            )
        return KnowledgeProviderResult(
            status=status,
            evidence=(
                KnowledgeEvidence(
                    provider=self.name,
                    revision=status.revision,
                    source=path.relative_to(self._root).as_posix(),
                    locator="full file",
                    content=content[: self._max_output_chars],
                ),
            ),
        )

    def _run(self, command: Sequence[str]) -> ProcessResult:
        return self._runner.run(
            command,
            stdin="",
            cwd=self._root,
            timeout_seconds=30,
        )


class P1KnowledgeProvider:
    name = "p1"

    def __init__(
        self,
        *,
        revision: str | None = None,
        query_handler: KnowledgeQueryHandler | None = None,
    ) -> None:
        self._revision = revision
        self._handler = query_handler

    def probe(self, repository: str, revision: str) -> KnowledgeProviderResult:
        del repository
        return self._probe(revision)

    def query(self, query: KnowledgeQuery) -> KnowledgeProviderResult:
        if query.operation is not KnowledgeOperation.P1_LOOKUP:
            raise ValueError("P1KnowledgeProvider only supports p1_lookup")
        return self._query(query)

    def _probe(self, revision: str) -> KnowledgeProviderResult:
        if self._handler is None or self._revision is None:
            return _result(
                self.name,
                ProviderStatus.UNAVAILABLE,
                diagnostics=(f"{self.name.upper()} adapter is not configured",),
            )
        if self._revision != revision:
            return _result(
                self.name,
                ProviderStatus.STALE,
                revision=self._revision,
                diagnostics=(
                    f"{self.name.upper()} revision does not match review revision",
                ),
            )
        return _result(self.name, ProviderStatus.READY, revision=self._revision)

    def _query(self, query: KnowledgeQuery) -> KnowledgeProviderResult:
        status = self._probe(query.revision).status
        if status.status is not ProviderStatus.READY or self._handler is None:
            return KnowledgeProviderResult(status=status)
        try:
            evidence = tuple(self._handler(query))
        except (OSError, RuntimeError, ValueError) as error:
            return _result(
                self.name,
                ProviderStatus.ERROR,
                revision=status.revision,
                diagnostics=(
                    f"{self.name.upper()} query failed: {type(error).__name__}",
                ),
            )
        return KnowledgeProviderResult(status=status, evidence=evidence)


class P2KnowledgeProvider(P1KnowledgeProvider):
    name = "p2"

    def query(self, query: KnowledgeQuery) -> KnowledgeProviderResult:
        if query.operation is not KnowledgeOperation.P2_LOOKUP:
            raise ValueError("P2KnowledgeProvider only supports p2_lookup")
        return self._query(query)


def _result(
    provider: str,
    status: ProviderStatus,
    *,
    revision: str | None = None,
    diagnostics: tuple[str, ...] = (),
) -> KnowledgeProviderResult:
    return KnowledgeProviderResult(
        status=ProviderStatusRef(
            provider=provider,
            status=status,
            revision=revision,
            diagnostics=diagnostics,
        )
    )


def _file_revision(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_repository_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("path must remain inside repository root") from error
    return candidate
