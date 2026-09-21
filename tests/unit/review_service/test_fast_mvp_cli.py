from __future__ import annotations

import io
import unittest

from arkui_agent.review_service.cli import build_parser, run
from arkui_agent.review_service.domain import (
    AgentReviewRequest,
    PullRequestContext,
    ReviewResult,
    ReviewResultStatus,
)
from arkui_agent.review_service.ports import SecretValue


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
    def get_pr_context(self, pr_id: int) -> PullRequestContext:
        if str(pr_id) != CONTEXT.pr_id:
            raise AssertionError("unexpected PR id")
        return CONTEXT


class StaticAgentRunner:
    def review(self, request: AgentReviewRequest) -> ReviewResult:
        return ReviewResult(
            status=ReviewResultStatus.SUCCESS,
            repository=request.repository,
            pr_id=request.pr_id,
            base_sha=request.base_sha,
            head_sha=request.head_sha,
            findings=(),
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


if __name__ == "__main__":
    unittest.main()
