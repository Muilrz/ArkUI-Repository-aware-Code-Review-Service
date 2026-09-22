from __future__ import annotations

import hashlib
import re
import subprocess
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType

from ..domain import ProviderStatus
from ..domain._validation import non_empty_string
from ..ports import KnowledgeGatewayError
from .knowledge import DocsKbProvider, LiveSourceProvider
from .process import ProcessResult, ProcessRunner, SubprocessRunner


class GitRevisionPreparer:
    """Prepare a detached, service-owned worktree without moving the main HEAD."""

    def __init__(
        self,
        root: Path,
        *,
        runtime_root: Path,
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self._root = root.resolve()
        self._runtime_root = runtime_root.resolve()
        self._runner = process_runner or SubprocessRunner()
        if self._runtime_root == self._root or self._root in self._runtime_root.parents:
            raise ValueError("runtime worktree root must be outside target repository")

    def update(self) -> None:
        self._run(("git", "fetch", "--no-tags", "origin"), cwd=self._root)

    def prepare(self, head_sha: str) -> AbstractContextManager[Path]:
        revision = non_empty_string(head_sha, field="head_sha")
        if re.fullmatch(r"[0-9a-fA-F]{40,64}", revision) is None:
            raise KnowledgeGatewayError("PR head is not a full Git commit SHA")
        return _PreparedRevision(self, revision.lower())

    def status(self) -> dict[str, str | None]:
        head = self._run(("git", "rev-parse", "HEAD"), cwd=self._root).stdout.strip()
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

    def _materialize(self, revision: str) -> Path:
        self.update()
        try:
            self._run(("git", "cat-file", "-e", f"{revision}^{{commit}}"), cwd=self._root)
        except KnowledgeGatewayError:
            self._run(("git", "fetch", "--no-tags", "origin", revision), cwd=self._root)
            self._run(("git", "cat-file", "-e", f"{revision}^{{commit}}"), cwd=self._root)
        path = self._runtime_root / (
            "revision-" + hashlib.sha256(revision.encode("utf-8")).hexdigest()[:20]
        )
        marker = self._marker(path)
        if path.exists():
            if not self._is_owned(marker):
                raise KnowledgeGatewayError("runtime worktree path is not service-owned")
            self._verify_registered(path)
            actual = self._run(("git", "rev-parse", "HEAD"), cwd=path).stdout.strip()
            if actual != revision:
                self._remove(path)
            else:
                self._verify_live(path, revision)
                return path
        if marker.exists() and not self._is_owned(marker):
            raise KnowledgeGatewayError("runtime worktree marker is not service-owned")
        try:
            self._runtime_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise KnowledgeGatewayError(
                f"runtime worktree directory failed: {type(error).__name__}"
            ) from None
        self._run(
            ("git", "worktree", "add", "--detach", str(path), revision),
            cwd=self._root,
        )
        try:
            marker.write_text(str(self._root), encoding="utf-8")
            self._verify_live(path, revision)
        except (OSError, KnowledgeGatewayError) as error:
            try:
                self._verify_registered(path)
                self._run(("git", "worktree", "remove", str(path)), cwd=self._root)
                marker.unlink(missing_ok=True)
            except (OSError, KnowledgeGatewayError) as cleanup_error:
                error.add_note(
                    f"runtime worktree cleanup failed: {type(cleanup_error).__name__}"
                )
            if isinstance(error, OSError):
                raise KnowledgeGatewayError(
                    f"runtime worktree verification failed: {type(error).__name__}"
                ) from None
            raise
        return path

    def _verify_registered(self, path: Path) -> None:
        listed = self._run(("git", "worktree", "list", "--porcelain"), cwd=self._root)
        registered = {
            Path(line[9:]).resolve()
            for line in listed.stdout.splitlines()
            if line.startswith("worktree ")
        }
        if path.resolve() not in registered or path.resolve() == self._root:
            raise KnowledgeGatewayError("runtime path is not a registered detached worktree")

    def _verify_live(self, path: Path, revision: str) -> None:
        live = LiveSourceProvider(
            path, process_runner=self._runner
        ).probe("", revision).status
        if live.status is not ProviderStatus.READY:
            raise KnowledgeGatewayError("prepared worktree is not clean at PR head")

    def _remove(self, path: Path) -> None:
        marker = self._marker(path)
        if not self._is_owned(marker):
            raise KnowledgeGatewayError("runtime worktree ownership cannot be verified")
        self._verify_registered(path)
        self._run(("git", "worktree", "remove", str(path)), cwd=self._root)
        try:
            marker.unlink()
        except OSError as error:
            raise KnowledgeGatewayError(
                f"runtime worktree marker cleanup failed: {type(error).__name__}"
            ) from None

    @staticmethod
    def _marker(path: Path) -> Path:
        return path.with_name(path.name + ".owner")

    def _is_owned(self, marker: Path) -> bool:
        try:
            return marker.is_file() and marker.read_text(encoding="utf-8") == str(self._root)
        except OSError as error:
            raise KnowledgeGatewayError(
                f"runtime worktree ownership check failed: {type(error).__name__}"
            ) from None

    def _run(self, command: tuple[str, ...], *, cwd: Path) -> ProcessResult:
        try:
            result = self._runner.run(
                command, stdin="", cwd=cwd, timeout_seconds=120
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


class _PreparedRevision(AbstractContextManager[Path]):
    def __init__(self, preparer: GitRevisionPreparer, revision: str) -> None:
        self._preparer = preparer
        self._revision = revision
        self._path: Path | None = None

    def __enter__(self) -> Path:
        self._path = self._preparer._materialize(self._revision)
        return self._path

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, traceback
        if self._path is not None:
            try:
                self._preparer._remove(self._path)
            except (KnowledgeGatewayError, OSError) as cleanup_error:
                if exc_value is None:
                    raise
                exc_value.add_note(
                    f"runtime worktree cleanup failed: {type(cleanup_error).__name__}"
                )
        return False
