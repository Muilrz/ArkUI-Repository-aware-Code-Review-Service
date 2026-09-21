from __future__ import annotations

import io
import unittest

from arkui_agent.review_service.cli import build_parser, run
from arkui_agent.review_service.domain import (
    AgentKnowledgeContext,
    AgentReviewRequest,
    ProviderStatus,
    ProviderStatusRef,
    PullRequestContext,
    ReviewResult,
    ReviewResultStatus,
)
from arkui_agent.review_service.ports import GitCodeProviderError, SecretValue


CONTEXT = PullRequestContext(
    repository="openharmony/arkui_ace_engine",
    pr_id="89521",
    title="fix gesture arbitration",
    author="hct95",
    base_sha="3a1b11c2ec8ead1440f6c71e90f7f8bcb9ecbd1a",
    head_sha="040cac089de659ae2b20e37e4f73c7e27b5281bf",
    changed_files=("frameworks/core/common/event_manager.cpp",),
    diff="@@ -10 +10 @@\n-old\n+new",
)


class StaticAdapter:
    def __init__(self, *, publish_error: bool = False) -> None:
        self.publish_error = publish_error
        self.published: list[tuple[str, str]] = []

    def get_pr_context(self, pr_id: int) -> PullRequestContext:
        if str(pr_id) != CONTEXT.pr_id:
            raise AssertionError("unexpected PR id")
        return CONTEXT

    def post_summary_comment(self, pr_id: str | int, body: str) -> str:
        if self.publish_error:
            raise GitCodeProviderError("comment endpoint rejected the request")
        self.published.append((str(pr_id), body))
        return "comment-42"


class StaticAgentRunner:
    last_request: AgentReviewRequest | None = None

    def review(self, request: AgentReviewRequest) -> ReviewResult:
        self.last_request = request
        return ReviewResult(
            status=ReviewResultStatus.SUCCESS,
            repository=request.repository,
            pr_id=request.pr_id,
            base_sha=request.base_sha,
            head_sha=request.head_sha,
            findings=(),
            degraded=(request.knowledge.degraded if request.knowledge else False),
            provider_statuses=(
                request.knowledge.provider_statuses if request.knowledge else ()
            ),
        )


class FastMvpCliTests(unittest.TestCase):
    def test_review_cli_uses_explicit_repository_and_prints_context(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        factory_calls: list[tuple[str, SecretValue | None]] = []

        def factory(repository: str, token: SecretValue | None) -> StaticAdapter:
            factory_calls.append((repository, token))
            return StaticAdapter()

        result = run(
            [
                "review",
                "--repository",
                "openharmony/arkui_ace_engine",
                "--pr",
                "89521",
            ],
            environ={},
            stdout=stdout,
            stderr=stderr,
            adapter_factory=factory,
        )

        self.assertEqual(result, 0)
        self.assertEqual(factory_calls, [("openharmony/arkui_ace_engine", None)])
        output = stdout.getvalue()
        for expected in (
            "repository: openharmony/arkui_ace_engine",
            "pr_id: 89521",
            "author: hct95",
            f"base_sha: {CONTEXT.base_sha}",
            f"head_sha: {CONTEXT.head_sha}",
            "changed_files: 1",
            "diff_size_bytes:",
        ):
            self.assertIn(expected, output)
        self.assertNotIn("diff:\n", output)
        self.assertEqual(stderr.getvalue(), "")

    def test_repository_env_token_redaction_and_show_diff(self) -> None:
        stdout = io.StringIO()
        secret_text = "private-token-value"
        observed_token: SecretValue | None = None

        def factory(repository: str, token: SecretValue | None) -> StaticAdapter:
            nonlocal observed_token
            self.assertEqual(repository, "openharmony/arkui_ace_engine")
            observed_token = token
            return StaticAdapter()

        result = run(
            ["review", "--pr", "89521", "--show-diff"],
            environ={
                "GITCODE_REPOSITORY": "openharmony/arkui_ace_engine",
                "GITCODE_TOKEN": secret_text,
            },
            stdout=stdout,
            adapter_factory=factory,
        )

        self.assertEqual(result, 0)
        self.assertIsInstance(observed_token, SecretValue)
        self.assertEqual(str(observed_token), "<redacted>")
        self.assertNotIn(secret_text, stdout.getvalue())
        self.assertIn("diff:\n", stdout.getvalue())
        self.assertIn(CONTEXT.diff, stdout.getvalue())

    def test_cli_rejects_non_positive_pr(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["review", "--pr", "0"])

    def test_agent_backend_prints_structured_review_result(self) -> None:
        stdout = io.StringIO()
        selected: list[str] = []

        def agent_factory(backend: str) -> StaticAgentRunner:
            selected.append(backend)
            return StaticAgentRunner()

        result = run(
            [
                "review",
                "--repository",
                CONTEXT.repository,
                "--pr",
                CONTEXT.pr_id,
                "--agent",
                "codex",
            ],
            environ={},
            stdout=stdout,
            adapter_factory=lambda repository, token: StaticAdapter(),
            agent_runner_factory=agent_factory,
        )

        self.assertEqual(result, 0)
        self.assertEqual(selected, ["codex"])
        parsed = ReviewResult.from_json(stdout.getvalue())
        self.assertEqual(parsed.head_sha, CONTEXT.head_sha)
        self.assertEqual(parsed.findings, ())

    def test_unsupported_backend_returns_clear_error(self) -> None:
        stderr = io.StringIO()

        result = run(
            [
                "review",
                "--repository",
                CONTEXT.repository,
                "--pr",
                CONTEXT.pr_id,
                "--agent",
                "claude",
            ],
            environ={},
            stderr=stderr,
            adapter_factory=lambda repository, token: StaticAdapter(),
        )

        self.assertEqual(result, 1)
        self.assertIn("unsupported agent backend: claude", stderr.getvalue())

    def test_repository_root_enables_knowledge_aware_agent_request(self) -> None:
        runner = StaticAgentRunner()
        statuses = (
            ProviderStatusRef("docs_kb", ProviderStatus.READY, "sha256:docs"),
            ProviderStatusRef(
                "live_source", ProviderStatus.READY, CONTEXT.head_sha
            ),
            ProviderStatusRef("p1", ProviderStatus.UNAVAILABLE),
            ProviderStatusRef("p2", ProviderStatus.UNAVAILABLE),
        )

        result = run(
            [
                "review",
                "--repository",
                CONTEXT.repository,
                "--pr",
                CONTEXT.pr_id,
                "--agent",
                "codex",
                "--repository-root",
                "C:/target/arkui",
            ],
            environ={},
            stdout=io.StringIO(),
            adapter_factory=lambda repository, token: StaticAdapter(),
            agent_runner_factory=lambda backend: runner,
            knowledge_context_factory=lambda context, root: AgentKnowledgeContext(
                repository_root=str(root),
                skill_path="C:/skill/SKILL.md",
                provider_statuses=statuses,
            ),
        )

        self.assertEqual(result, 0)
        self.assertIsNotNone(runner.last_request)
        self.assertEqual(runner.last_request.knowledge.provider_statuses, statuses)

    def test_agent_review_without_publish_never_calls_write_api(self) -> None:
        adapter = StaticAdapter(publish_error=True)

        result = run(
            [
                "review",
                "--repository",
                CONTEXT.repository,
                "--pr",
                CONTEXT.pr_id,
                "--agent",
                "codex",
            ],
            environ={},
            stdout=io.StringIO(),
            adapter_factory=lambda repository, token: adapter,
            agent_runner_factory=lambda backend: StaticAgentRunner(),
        )

        self.assertEqual(result, 0)
        self.assertEqual(adapter.published, [])

    def test_publish_posts_to_requested_pr_only_with_explicit_opt_in(self) -> None:
        adapter = StaticAdapter()
        stdout = io.StringIO()
        secret = "private-token-value"

        result = run(
            [
                "review",
                "--repository",
                CONTEXT.repository,
                "--pr",
                CONTEXT.pr_id,
                "--agent",
                "codex",
                "--publish",
            ],
            environ={"GITCODE_TOKEN": secret},
            stdout=stdout,
            adapter_factory=lambda repository, token: adapter,
            agent_runner_factory=lambda backend: StaticAgentRunner(),
        )

        self.assertEqual(result, 0)
        self.assertEqual(len(adapter.published), 1)
        pr_id, body = adapter.published[0]
        self.assertEqual(pr_id, CONTEXT.pr_id)
        self.assertIn("No issues with sufficient evidence were found", body)
        self.assertNotIn(secret, body)
        self.assertIn("published_comment_id: comment-42", stdout.getvalue())
        self.assertNotIn(secret, stdout.getvalue())

    def test_publish_failure_is_not_reported_as_review_success(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        result = run(
            [
                "review",
                "--repository",
                CONTEXT.repository,
                "--pr",
                CONTEXT.pr_id,
                "--agent",
                "codex",
                "--publish",
            ],
            environ={"GITCODE_TOKEN": "private-token-value"},
            stdout=stdout,
            stderr=stderr,
            adapter_factory=lambda repository, token: StaticAdapter(
                publish_error=True
            ),
            agent_runner_factory=lambda backend: StaticAgentRunner(),
        )

        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("GitCode provider failed", stderr.getvalue())

    def test_publish_requires_agent_before_reading_pr(self) -> None:
        factory_called = False

        def factory(repository: str, token: SecretValue | None) -> StaticAdapter:
            nonlocal factory_called
            factory_called = True
            return StaticAdapter()

        stderr = io.StringIO()
        result = run(
            [
                "review",
                "--repository",
                CONTEXT.repository,
                "--pr",
                CONTEXT.pr_id,
                "--publish",
            ],
            environ={},
            stderr=stderr,
            adapter_factory=factory,
        )

        self.assertEqual(result, 1)
        self.assertFalse(factory_called)
        self.assertIn("--publish requires --agent", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
