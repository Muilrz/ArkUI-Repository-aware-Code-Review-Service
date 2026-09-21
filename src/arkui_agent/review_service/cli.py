from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TextIO

from .adapters import CodexAgentRunner, GitCodeRestAdapter
from .application import (
    CodeAgentReviewService,
    build_agent_output_schema,
    build_diff_review_prompt,
)
from .domain import PullRequestContext, ReviewResult
from .ports import CodeAgentRunner, ReviewServiceError, SecretValue


class PullRequestContextReader(Protocol):
    def get_pr_context(self, pr_id: str | int) -> PullRequestContext:
        """Return one revision-bound PR context."""
        ...


AdapterFactory = Callable[[str, SecretValue | None], PullRequestContextReader]
AgentRunnerFactory = Callable[[str], CodeAgentRunner]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arkui-review")
    subparsers = parser.add_subparsers(dest="command", required=True)
    review = subparsers.add_parser(
        "review",
        help="read and print one GitCode pull request context",
    )
    review.add_argument(
        "--repository",
        help="GitCode repository in owner/repo format; defaults to GITCODE_REPOSITORY",
    )
    review.add_argument("--pr", required=True, type=_positive_integer)
    review.add_argument(
        "--show-diff",
        action="store_true",
        help="print the combined pull request diff",
    )
    review.add_argument(
        "--agent",
        help="run a structured review with the selected backend (currently: codex)",
    )
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    adapter_factory: AdapterFactory | None = None,
    agent_runner_factory: AgentRunnerFactory | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    environment = os.environ if environ is None else environ
    output = sys.stdout if stdout is None else stdout
    errors = sys.stderr if stderr is None else stderr

    repository = args.repository or environment.get("GITCODE_REPOSITORY")
    if not repository:
        parser.error("--repository or GITCODE_REPOSITORY is required")
    token_text = environment.get("GITCODE_TOKEN")
    token = SecretValue(token_text) if token_text else None
    factory = adapter_factory or _create_adapter

    try:
        context = factory(repository, token).get_pr_context(args.pr)
    except (ReviewServiceError, ValueError) as error:
        print(f"error: {error}", file=errors)
        return 1

    if args.agent is not None:
        runner_factory = agent_runner_factory or _create_agent_runner
        try:
            result = CodeAgentReviewService(runner_factory(args.agent)).review(context)
        except (ReviewServiceError, ValueError) as error:
            print(f"error: {error}", file=errors)
            return 1
        _print_review_result(result, output)
        return 0

    print(f"repository: {context.repository}", file=output)
    print(f"pr_id: {context.pr_id}", file=output)
    print(f"title: {context.title}", file=output)
    print(f"author: {context.author}", file=output)
    print(f"base_sha: {context.base_sha}", file=output)
    print(f"head_sha: {context.head_sha}", file=output)
    print(f"changed_files: {len(context.changed_files)}", file=output)
    print(f"diff_size_bytes: {len(context.diff.encode('utf-8'))}", file=output)
    if args.show_diff:
        print("diff:", file=output)
        print(context.diff, file=output)
    return 0


def main() -> int:
    return run()


def _create_adapter(
    repository: str, access_token: SecretValue | None
) -> GitCodeRestAdapter:
    return GitCodeRestAdapter(repository=repository, access_token=access_token)


def _create_agent_runner(backend: str) -> CodeAgentRunner:
    if backend != "codex":
        raise ValueError(f"unsupported agent backend: {backend}")
    return CodexAgentRunner(
        prompt_builder=build_diff_review_prompt,
        schema_builder=build_agent_output_schema,
    )


def _print_review_result(result: ReviewResult, output: TextIO) -> None:
    print(result.to_json(), file=output)


def _positive_integer(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


if __name__ == "__main__":
    raise SystemExit(main())
