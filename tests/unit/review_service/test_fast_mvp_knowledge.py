from __future__ import annotations

import tempfile
import sys
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path

from arkui_agent.review_service.adapters import (
    DocsKbProvider,
    LiveSourceProvider,
    P1KnowledgeProvider,
    P2KnowledgeProvider,
    ProcessResult,
)
from arkui_agent.review_service.application import ReviewKnowledgeFacade
from arkui_agent.review_service.domain import (
    KnowledgeOperation,
    KnowledgeQuery,
    ProviderStatus,
)
from arkui_agent.review_service.ports import KnowledgeGatewayError


REPOSITORY = "openharmony/arkui_ace_engine"
REVISION = "040cac089de659ae2b20e37e4f73c7e27b5281bf"


class CommandProcessRunner:
    def __init__(self, results: Mapping[tuple[str, ...], ProcessResult]) -> None:
        self.results = dict(results)
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        command: Sequence[str],
        *,
        stdin: str,
        cwd: Path,
        timeout_seconds: float,
        environment: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        del stdin, cwd, timeout_seconds, environment
        key = tuple(command)
        self.calls.append(key)
        try:
            return self.results[key]
        except KeyError as error:
            raise AssertionError(f"unexpected command: {key}") from error


class FastMvpKnowledgeTests(unittest.TestCase):
    def test_docs_kb_search_returns_versioned_provider_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "kb_search.py").write_text("", encoding="utf-8")
            (root / "docs" / "context_registry.json").write_text(
                "{}", encoding="utf-8"
            )
            command = (
                sys.executable,
                "docs/kb_search.py",
                "GestureRecognizer",
                "--detail",
            )
            runner = CommandProcessRunner(
                {command: ProcessResult(0, "EventBaseFramework", "")}
            )
            provider = DocsKbProvider(root, process_runner=runner)

            result = provider.query(
                KnowledgeQuery(
                    REPOSITORY,
                    REVISION,
                    KnowledgeOperation.DOCS_SEARCH,
                    "GestureRecognizer",
                )
            )

            self.assertEqual(result.status.status, ProviderStatus.READY)
            self.assertTrue(result.status.revision.startswith("sha256:"))
            self.assertEqual(result.evidence[0].provider, "docs_kb")
            self.assertIn("EventBaseFramework", result.evidence[0].content)

    def test_live_source_requires_exact_clean_revision_before_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            search = (
                "rg",
                "--line-number",
                "--column",
                "--fixed-strings",
                "--max-count",
                "20",
                "--",
                "IsEscapedToManager",
            )
            runner = CommandProcessRunner(
                {
                    ("git", "rev-parse", "HEAD"): ProcessResult(
                        0, REVISION + "\n", ""
                    ),
                    (
                        "git",
                        "status",
                        "--porcelain",
                        "--untracked-files=no",
                    ): ProcessResult(0, "", ""),
                    search: ProcessResult(
                        0, "recognizer.cpp:20:3:IsEscapedToManager", ""
                    ),
                }
            )
            provider = LiveSourceProvider(root, process_runner=runner)

            result = provider.query(
                KnowledgeQuery(
                    REPOSITORY,
                    REVISION,
                    KnowledgeOperation.LIVE_SEARCH,
                    "IsEscapedToManager",
                )
            )

            self.assertEqual(result.status.status, ProviderStatus.READY)
            self.assertEqual(result.status.revision, REVISION)
            self.assertEqual(result.evidence[0].revision, REVISION)
            self.assertIn(search, runner.calls)

    def test_stale_live_source_does_not_run_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = CommandProcessRunner(
                {
                    ("git", "rev-parse", "HEAD"): ProcessResult(
                        0, "different\n", ""
                    )
                }
            )
            provider = LiveSourceProvider(Path(directory), process_runner=runner)

            result = provider.query(
                KnowledgeQuery(
                    REPOSITORY,
                    REVISION,
                    KnowledgeOperation.LIVE_SEARCH,
                    "symbol",
                )
            )

            self.assertEqual(result.status.status, ProviderStatus.STALE)
            self.assertEqual(len(runner.calls), 1)

    def test_optional_p1_p2_degrade_without_blocking_facade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "kb_search.py").write_text("", encoding="utf-8")
            (root / "docs" / "context_registry.json").write_text(
                "{}", encoding="utf-8"
            )
            docs_command = (
                sys.executable,
                "docs/kb_search.py",
                "gesture",
                "--detail",
            )
            docs = DocsKbProvider(
                root,
                process_runner=CommandProcessRunner(
                    {docs_command: ProcessResult(0, "gesture kb", "")}
                ),
            )
            live = LiveSourceProvider(
                root,
                process_runner=CommandProcessRunner(
                    {
                        ("git", "rev-parse", "HEAD"): ProcessResult(
                            0, REVISION, ""
                        ),
                        (
                            "git",
                            "status",
                            "--porcelain",
                            "--untracked-files=no",
                        ): ProcessResult(0, "", ""),
                    }
                ),
            )
            facade = ReviewKnowledgeFacade(
                {
                    "docs_kb": docs,
                    "live_source": live,
                    "p1": P1KnowledgeProvider(),
                    "p2": P2KnowledgeProvider(),
                }
            )

            context = facade.prepare(
                repository=REPOSITORY,
                revision=REVISION,
                docs_query="gesture",
            )

            self.assertTrue(context.degraded)
            statuses = {
                item.provider: item.status for item in context.provider_statuses
            }
            self.assertEqual(statuses["docs_kb"], ProviderStatus.READY)
            self.assertEqual(statuses["live_source"], ProviderStatus.READY)
            self.assertEqual(statuses["p1"], ProviderStatus.UNAVAILABLE)
            self.assertEqual(statuses["p2"], ProviderStatus.UNAVAILABLE)

    def test_facade_fails_when_live_source_revision_is_stale(self) -> None:
        class NeverCalledProvider:
            name = "docs_kb"

            def probe(self, repository: str, revision: str):
                raise AssertionError("docs must not run before Live Source gate")

            def query(self, query: KnowledgeQuery):
                raise AssertionError("docs must not run before Live Source gate")

        with tempfile.TemporaryDirectory() as directory:
            live = LiveSourceProvider(
                Path(directory),
                process_runner=CommandProcessRunner(
                    {
                        ("git", "rev-parse", "HEAD"): ProcessResult(
                            0, "different", ""
                        )
                    }
                ),
            )
            facade = ReviewKnowledgeFacade(
                {
                    "docs_kb": NeverCalledProvider(),
                    "live_source": live,
                    "p1": P1KnowledgeProvider(),
                    "p2": P2KnowledgeProvider(),
                }
            )

            with self.assertRaises(KnowledgeGatewayError):
                facade.prepare(
                    repository=REPOSITORY,
                    revision=REVISION,
                    docs_query="gesture",
                )

    def test_skill_is_agent_neutral_and_references_resolve(self) -> None:
        root = Path(__file__).parents[3]
        skill_root = root / "skills" / "arkui-code-review"
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")

        self.assertNotIn("codex", skill_text.lower())
        self.assertTrue((skill_root / "references" / "knowledge-tools.md").is_file())
        self.assertTrue((skill_root / "references" / "result-contract.md").is_file())


if __name__ == "__main__":
    unittest.main()
