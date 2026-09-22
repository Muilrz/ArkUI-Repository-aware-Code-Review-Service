from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol, TextIO

from .adapters import (
    CodexAgentRunner,
    DocsKbProvider,
    GitCodeRestAdapter,
    GitRevisionPreparer,
    LiveSourceProvider,
    P1KnowledgeProvider,
    P2KnowledgeProvider,
    SqliteReviewState,
)
from .application import (
    AutoReviewService,
    CodeAgentReviewService,
    ReviewPublishingService,
    ReviewKnowledgeFacade,
    build_agent_output_schema,
    build_diff_review_prompt,
)
from .domain import (
    AgentKnowledgeContext,
    PullRequestContext,
    PullRequestSummary,
    ReviewResult,
)
from .ports import (
    CodeAgentRunner,
    ReviewConfigurationError,
    ReviewServiceError,
    SecretValue,
)


class PullRequestContextReader(Protocol):
    def list_open_prs(self, *, limit: int = 20) -> tuple[PullRequestSummary, ...]:
        """Return recent open pull-request summaries for polling."""
        ...

    def get_pr_context(self, pr_id: str | int) -> PullRequestContext:
        """Return one revision-bound PR context."""
        ...

    def post_summary_comment(self, pr_id: str | int, body: str) -> str:
        """Publish one summary comment and return its platform identifier."""
        ...


AdapterFactory = Callable[[str, SecretValue | None], PullRequestContextReader]
AgentRunnerFactory = Callable[[str], CodeAgentRunner]
KnowledgeContextFactory = Callable[
    [PullRequestContext, Path], AgentKnowledgeContext
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arkui-review")
    subparsers = parser.add_subparsers(dest="command", required=True)
    review = subparsers.add_parser(
        "review",
        help="read a GitCode PR and optionally run or publish a review",
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
    review.add_argument(
        "--repository-root",
        help="target Git worktree at the PR head; defaults to ARKUI_REPO_ROOT",
    )
    review.add_argument(
        "--publish",
        action="store_true",
        help="explicitly publish the formatted review as one GitCode PR comment",
    )
    poll = subparsers.add_parser("poll", help="run the M5 automatic review loop")
    poll.add_argument("--repository", help="defaults to GITCODE_REPOSITORY")
    poll.add_argument("--repository-root", help="defaults to ARKUI_REPO_ROOT")
    poll.add_argument("--authors", help="comma-separated whitelist; defaults to ARKUI_REVIEW_AUTHORS")
    poll.add_argument("--interval", type=_positive_integer, help="seconds; defaults to ARKUI_REVIEW_POLL_INTERVAL or 600")
    poll.add_argument("--policy-version", help="defaults to ARKUI_REVIEW_POLICY_VERSION or v1")
    poll.add_argument("--state", help="SQLite path; defaults to var/review-state.sqlite")
    poll.add_argument("--worktree-cache", help="detached runtime worktrees; defaults to var/worktrees")
    poll.add_argument("--agent", default="codex")
    poll.add_argument("--once", action="store_true", help="run one cycle and exit")
    knowledge = subparsers.add_parser("knowledge", help="inspect or update target repository knowledge")
    knowledge.add_argument("action", choices=("update", "status"))
    knowledge.add_argument("--repository-root", help="defaults to ARKUI_REPO_ROOT")
    knowledge.add_argument("--worktree-cache", help="detached runtime worktrees; defaults to var/worktrees")
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    adapter_factory: AdapterFactory | None = None,
    agent_runner_factory: AgentRunnerFactory | None = None,
    knowledge_context_factory: KnowledgeContextFactory | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    environment = os.environ if environ is None else environ
    output = sys.stdout if stdout is None else stdout
    errors = sys.stderr if stderr is None else stderr

    if args.command == "knowledge":
        try:
            root = _required_root(args.repository_root, environment)
            preparer = GitRevisionPreparer(
                root, runtime_root=Path(args.worktree_cache or "var/worktrees")
            )
            if args.action == "update":
                preparer.update()
            print(json.dumps(preparer.status(), sort_keys=True), file=output)
            return 0
        except (ReviewServiceError, ValueError) as error:
            print(f"error: {error}", file=errors)
            return 1
    if args.command == "poll":
        try:
            return _run_poll(args, environment, output, adapter_factory, agent_runner_factory, knowledge_context_factory)
        except (ReviewServiceError, ValueError) as error:
            print(f"error: {error}", file=errors)
            return 1

    repository = args.repository or environment.get("GITCODE_REPOSITORY")
    if not repository:
        parser.error("--repository or GITCODE_REPOSITORY is required")
    if args.publish and args.agent is None:
        print("error: --publish requires --agent", file=errors)
        return 1
    token_text = environment.get("GITCODE_TOKEN")
    token = SecretValue(token_text) if token_text else None
    factory = adapter_factory or _create_adapter

    try:
        adapter = factory(repository, token)
        context = adapter.get_pr_context(args.pr)
    except (ReviewServiceError, ValueError) as error:
        print(f"error: {error}", file=errors)
        return 1

    if args.agent is not None:
        runner_factory = agent_runner_factory or _create_agent_runner
        try:
            repository_root = args.repository_root or environment.get(
                "ARKUI_REPO_ROOT"
            )
            knowledge = (
                None
                if repository_root is None
                else (knowledge_context_factory or _prepare_knowledge_context)(
                    context, Path(repository_root)
                )
            )
            result = CodeAgentReviewService(runner_factory(args.agent)).review(
                context,
                knowledge=knowledge,
            )
            comment_id = (
                ReviewPublishingService(adapter).publish(result)
                if args.publish
                else None
            )
        except (ReviewServiceError, ValueError) as error:
            print(f"error: {error}", file=errors)
            return 1
        _print_review_result(result, output)
        if comment_id is not None:
            print(f"published_comment_id: {comment_id}", file=output)
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


def _prepare_knowledge_context(
    context: PullRequestContext, repository_root: Path
) -> AgentKnowledgeContext:
    resolved_root = repository_root.resolve()
    facade = ReviewKnowledgeFacade(
        {
            "docs_kb": DocsKbProvider(resolved_root),
            "live_source": LiveSourceProvider(resolved_root),
            "p1": P1KnowledgeProvider(),
            "p2": P2KnowledgeProvider(),
        }
    )
    knowledge = facade.prepare(
        repository=context.repository,
        revision=context.head_sha,
        docs_query=context.title,
    )
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "arkui-code-review"
        / "SKILL.md"
    )
    if not skill_path.is_file():
        raise ValueError("ArkUI review skill is unavailable")
    return AgentKnowledgeContext(
        repository_root=str(resolved_root),
        skill_path=str(skill_path),
        provider_statuses=knowledge.provider_statuses,
        initial_evidence=knowledge.evidence,
    )


def _print_review_result(result: ReviewResult, output: TextIO) -> None:
    print(result.to_json(), file=output)


def _required_root(value: str | None, environment: Mapping[str, str]) -> Path:
    raw = value or environment.get("ARKUI_REPO_ROOT")
    if not raw:
        raise ReviewConfigurationError("ARKUI_REPO_ROOT is required")
    root = Path(raw).resolve()
    if not root.is_dir():
        raise ReviewConfigurationError("target repository root is unavailable")
    return root


def _run_poll(
    args: argparse.Namespace,
    environment: Mapping[str, str],
    output: TextIO,
    adapter_factory: AdapterFactory | None,
    agent_runner_factory: AgentRunnerFactory | None,
    knowledge_context_factory: KnowledgeContextFactory | None,
) -> int:
    repository = args.repository or environment.get("GITCODE_REPOSITORY")
    if not repository:
        raise ReviewConfigurationError("GITCODE_REPOSITORY is required")
    token_text = environment.get("GITCODE_TOKEN")
    if not token_text:
        raise ReviewConfigurationError("GITCODE_TOKEN is required for polling")
    root = _required_root(args.repository_root, environment)
    raw_authors = args.authors or environment.get("ARKUI_REVIEW_AUTHORS", "")
    authors = frozenset(name.strip() for name in raw_authors.split(",") if name.strip())
    if not authors:
        raise ReviewConfigurationError("ARKUI_REVIEW_AUTHORS must not be empty")
    raw_interval = args.interval or environment.get("ARKUI_REVIEW_POLL_INTERVAL", "600")
    try:
        interval = _positive_integer(str(raw_interval))
    except argparse.ArgumentTypeError as error:
        raise ReviewConfigurationError("poll interval must be a positive integer") from error
    policy = args.policy_version or environment.get("ARKUI_REVIEW_POLICY_VERSION", "v1")
    state_path = Path(args.state or "var/review-state.sqlite")
    adapter = (adapter_factory or _create_adapter)(repository, SecretValue(token_text))
    runner = (agent_runner_factory or _create_agent_runner)(args.agent)
    preparer = GitRevisionPreparer(
        root, runtime_root=Path(args.worktree_cache or "var/worktrees")
    )
    service = AutoReviewService(
        gitcode=adapter,
        state=SqliteReviewState(state_path),
        preparer=preparer,
        authors=authors,
        policy_version=policy,
        knowledge_context=lambda context, prepared_root: (
            knowledge_context_factory or _prepare_knowledge_context
        )(context, prepared_root),
        review=lambda context, knowledge: CodeAgentReviewService(runner).review(
            context, knowledge=knowledge
        ),
        publish=ReviewPublishingService(adapter).publish,
    )
    last_daily_refresh: float | None = None
    while True:
        now = time.monotonic()
        if last_daily_refresh is None or now - last_daily_refresh >= 86_400:
            preparer.update()
            preparer.status()
            last_daily_refresh = now
        cycle = service.poll_once()
        print(
            json.dumps(
                {
                    "discovered": cycle.discovered,
                    "filtered": cycle.filtered,
                    "deduplicated": cycle.deduplicated,
                    "published_comment_ids": [
                        comment_id for _, comment_id in cycle.published
                    ],
                }, sort_keys=True
            ),
            file=output,
            flush=True,
        )
        if args.once:
            return 0
        time.sleep(interval)


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
