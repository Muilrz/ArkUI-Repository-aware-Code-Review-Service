from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arkui_agent.review_service.adapters import GitRevisionPreparer, ProcessResult
from arkui_agent.review_service.ports import KnowledgeGatewayError


class FakeGitProcess:
    def __init__(self, head: str = "head-a", *, fetch_code: int = 0) -> None:
        self.head = head
        self.fetch_code = fetch_code
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, *, stdin, cwd, timeout_seconds, environment=None):
        command = tuple(command)
        self.commands.append(command)
        if command[:2] == ("git", "fetch"):
            return ProcessResult(self.fetch_code, "", "private stderr")
        if command == ("git", "rev-parse", "HEAD"):
            return ProcessResult(0, self.head + "\n", "")
        if command[:2] == ("git", "status"):
            return ProcessResult(0, "", "")
        raise AssertionError(f"unexpected command: {command}")


class GitRevisionPreparerTests(unittest.TestCase):
    def test_fetch_then_verify_exact_head_and_clean_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            process = FakeGitProcess()
            preparer = GitRevisionPreparer(Path(directory), process_runner=process)
            preparer.prepare("head-a")
            self.assertEqual(process.commands[0], ("git", "fetch", "--no-tags", "origin"))
            self.assertIn(("git", "rev-parse", "HEAD"), process.commands)
            self.assertTrue(any(command[:2] == ("git", "status") for command in process.commands))

    def test_mismatched_head_and_fetch_failure_fail_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mismatch = GitRevisionPreparer(
                Path(directory), process_runner=FakeGitProcess(head="other")
            )
            with self.assertRaises(KnowledgeGatewayError):
                mismatch.prepare("head-a")
            failure = GitRevisionPreparer(
                Path(directory), process_runner=FakeGitProcess(fetch_code=1)
            )
            with self.assertRaises(KnowledgeGatewayError) as captured:
                failure.prepare("head-a")
            self.assertNotIn("private stderr", captured.exception.reason)

    def test_status_reports_docs_and_live_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "docs" / "context_registry.json"
            registry.parent.mkdir()
            registry.write_text("{}", encoding="utf-8")
            (root / "docs" / "kb_search.py").write_text("", encoding="utf-8")
            status = GitRevisionPreparer(
                root, process_runner=FakeGitProcess()
            ).status()
            self.assertEqual(status["head_sha"], "head-a")
            self.assertEqual(status["docs_kb_status"], "ready")
            self.assertEqual(status["live_source_status"], "ready")
            self.assertTrue(status["docs_kb_revision"].startswith("sha256:"))
