from __future__ import annotations

import subprocess
import tempfile
import unittest
import io
from pathlib import Path

from arkui_agent.review_service.adapters import GitRevisionPreparer
from arkui_agent.review_service.cli import run
from arkui_agent.review_service.domain import (
    AgentKnowledgeContext,
    AgentReviewRequest,
    ProviderStatus,
    ProviderStatusRef,
    PullRequestContext,
    ReviewResult,
    ReviewResultStatus,
)
from arkui_agent.review_service.ports import KnowledgeGatewayError


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ("git", *args), cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode:
        raise AssertionError(f"local Git fixture failed: {args[0]}")
    return result.stdout.strip()


class GitRevisionPreparerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.remote = base / "remote.git"
        self.author = base / "author"
        self.target = base / "target"
        self.runtime = base / "runtime"
        git("init", "--bare", "--initial-branch=main", str(self.remote))
        git("clone", str(self.remote), str(self.author))
        (self.author / "docs").mkdir()
        (self.author / "docs" / "context_registry.json").write_text("{}", encoding="utf-8")
        (self.author / "docs" / "kb_search.py").write_text("", encoding="utf-8")
        (self.author / "a.cpp").write_text("old", encoding="utf-8")
        git("add", ".", cwd=self.author)
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-m", "first", cwd=self.author)
        git("push", "origin", "HEAD:main", cwd=self.author)
        git("clone", str(self.remote), str(self.target))
        self.main_head = git("rev-parse", "HEAD", cwd=self.target)
        (self.author / "a.cpp").write_text("new", encoding="utf-8")
        git("add", ".", cwd=self.author)
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-m", "second", cwd=self.author)
        git("push", "origin", "HEAD:main", cwd=self.author)
        self.target_head = git("rev-parse", "HEAD", cwd=self.author)

    def test_detached_revision_without_switching_main_head_and_cleanup(self) -> None:
        preparer = GitRevisionPreparer(self.target, runtime_root=self.runtime)
        with preparer.prepare(self.target_head) as prepared:
            self.assertEqual(git("rev-parse", "HEAD", cwd=prepared), self.target_head)
            self.assertEqual((prepared / "a.cpp").read_text(encoding="utf-8"), "new")
            self.assertEqual((self.target / "a.cpp").read_text(encoding="utf-8"), "old")
            self.assertEqual(git("rev-parse", "HEAD", cwd=self.target), self.main_head)
            self.assertTrue((prepared / "docs" / "kb_search.py").is_file())
        self.assertFalse(prepared.exists())
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.target), self.main_head)

    def test_existing_stale_service_worktree_is_safely_rebuilt(self) -> None:
        preparer = GitRevisionPreparer(self.target, runtime_root=self.runtime)
        stale = preparer._materialize(self.target_head)
        git("checkout", "--detach", self.main_head, cwd=stale)
        with preparer.prepare(self.target_head) as prepared:
            self.assertEqual(prepared, stale)
            self.assertEqual(git("rev-parse", "HEAD", cwd=prepared), self.target_head)
        self.assertFalse(stale.exists())

    def test_existing_correct_service_worktree_is_reused(self) -> None:
        preparer = GitRevisionPreparer(self.target, runtime_root=self.runtime)
        existing = preparer._materialize(self.target_head)
        with preparer.prepare(self.target_head) as prepared:
            self.assertEqual(prepared, existing)
            self.assertEqual(git("rev-parse", "HEAD", cwd=prepared), self.target_head)
        self.assertFalse(existing.exists())

    def test_unowned_path_and_unknown_revision_fail_without_main_checkout(self) -> None:
        preparer = GitRevisionPreparer(self.target, runtime_root=self.runtime)
        with self.assertRaises(KnowledgeGatewayError):
            with preparer.prepare("0" * 40):
                self.fail("unknown revision must not be prepared")
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.target), self.main_head)

        owned = preparer._materialize(self.target_head)
        preparer._marker(owned).unlink()
        with self.assertRaises(KnowledgeGatewayError):
            with preparer.prepare(self.target_head):
                self.fail("unowned worktree must not be reused")
        # Restore the test-created marker solely so the service can clean up.
        preparer._marker(owned).write_text(str(self.target.resolve()), encoding="utf-8")
        preparer._remove(owned)

    def test_cleanup_failure_does_not_hide_original_review_error(self) -> None:
        class CleanupFailure(GitRevisionPreparer):
            def _remove(self, path: Path) -> None:
                raise KnowledgeGatewayError("cleanup failed")

        preparer = CleanupFailure(self.target, runtime_root=self.runtime)
        prepared_path: Path | None = None
        with self.assertRaisesRegex(RuntimeError, "original review error") as captured:
            with preparer.prepare(self.target_head) as prepared_path:
                raise RuntimeError("original review error")
        self.assertTrue(any("cleanup failed" in note for note in captured.exception.__notes__))
        # The test-owned worktree is removed explicitly after asserting the error.
        self.assertIsNotNone(prepared_path)
        GitRevisionPreparer(self.target, runtime_root=self.runtime)._remove(prepared_path)

    def test_manual_review_uses_detached_head_and_keeps_main_checkout(self) -> None:
        context = PullRequestContext(
            repository="owner/repo", pr_id="1", title="change", author="author",
            base_sha=self.main_head, head_sha=self.target_head,
            changed_files=("a.cpp",), diff="@@ -1 +1 @@\n-old\n+new",
        )
        prepared_paths: list[Path] = []

        class Adapter:
            def get_pr_context(self, pr_id: str | int) -> PullRequestContext:
                if str(pr_id) != "1":
                    raise AssertionError("wrong PR")
                return context

        class Runner:
            def review(self, request: AgentReviewRequest) -> ReviewResult:
                assert request.knowledge is not None
                root = Path(request.knowledge.repository_root)
                prepared_paths.append(root)
                if git("rev-parse", "HEAD", cwd=root) != context.head_sha:
                    raise AssertionError("Agent did not receive PR head")
                if (root / "a.cpp").read_text(encoding="utf-8") != "new":
                    raise AssertionError("Agent did not receive updated source")
                return ReviewResult(
                    ReviewResultStatus.SUCCESS, request.repository, request.pr_id,
                    request.base_sha, request.head_sha, (),
                    request.knowledge.degraded, request.knowledge.provider_statuses,
                )

        def knowledge(pr: PullRequestContext, root: Path) -> AgentKnowledgeContext:
            self.assertEqual(pr.head_sha, self.target_head)
            self.assertEqual(git("rev-parse", "HEAD", cwd=root), self.target_head)
            return AgentKnowledgeContext(
                repository_root=str(root), skill_path="SKILL.md",
                provider_statuses=(
                    ProviderStatusRef("docs_kb", ProviderStatus.READY, "sha256:docs"),
                    ProviderStatusRef("live_source", ProviderStatus.READY, pr.head_sha),
                    ProviderStatusRef("p1", ProviderStatus.UNAVAILABLE),
                    ProviderStatusRef("p2", ProviderStatus.UNAVAILABLE),
                ),
            )

        output = io.StringIO()
        result = run(
            ["review", "--repository", context.repository, "--pr", "1",
             "--agent", "codex", "--repository-root", str(self.target),
             "--worktree-cache", str(self.runtime)],
            environ={}, stdout=output,
            adapter_factory=lambda repository, token: Adapter(),
            agent_runner_factory=lambda backend: Runner(),
            knowledge_context_factory=knowledge,
        )
        self.assertEqual(result, 0)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.target), self.main_head)
        self.assertEqual(len(prepared_paths), 1)
        self.assertFalse(prepared_paths[0].exists())
        self.assertEqual(ReviewResult.from_json(output.getvalue()).head_sha, self.target_head)
