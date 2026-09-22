from __future__ import annotations

import subprocess
from pathlib import Path

from ..domain import ProviderStatus
from ..domain._validation import non_empty_string
from ..ports import KnowledgeGatewayError
from .knowledge import DocsKbProvider, LiveSourceProvider
from .process import ProcessResult, ProcessRunner, SubprocessRunner


class GitRevisionPreparer:
    """Fetch Git metadata, then require an already-aligned clean worktree.

    M5 deliberately never checks out or edits target source. A mismatched HEAD
    needs an explicitly prepared external worktree; it is not silently guessed.
    """

    def __init__(
        self, root: Path, *, process_runner: ProcessRunner | None = None
    ) -> None:
        self._root = root.resolve()
        self._runner = process_runner or SubprocessRunner()

    def update(self) -> None:
        self._run(("git", "fetch", "--no-tags", "origin"))

    def prepare(self, head_sha: str) -> None:
        revision = non_empty_string(head_sha, field="head_sha")
        self.update()
        live = LiveSourceProvider(
            self._root, process_runner=self._runner
        ).probe("", revision).status
        if live.status is not ProviderStatus.READY:
            raise KnowledgeGatewayError(
                "Live Source worktree is not clean and aligned to PR head"
            )

    def status(self) -> dict[str, str | None]:
        head = self._run(("git", "rev-parse", "HEAD")).stdout.strip()
        docs = DocsKbProvider(self._root).probe("", head).status
        live = LiveSourceProvider(
            self._root, process_runner=self._runner
        ).probe("", head).status
        return {
            "head_sha": head,
            "docs_kb_status": docs.status.value,
            "docs_kb_revision": docs.revision,
            "live_source_status": live.status.value,
            "live_source_revision": live.revision,
        }

    def _run(self, command: tuple[str, ...]) -> ProcessResult:
        try:
            result = self._runner.run(
                command, stdin="", cwd=self._root, timeout_seconds=120
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise KnowledgeGatewayError(
                f"Git revision operation failed: {type(error).__name__}"
            ) from None
        if result.exit_code != 0:
            raise KnowledgeGatewayError(
                f"Git revision operation exited with code {result.exit_code}"
            )
        return result
