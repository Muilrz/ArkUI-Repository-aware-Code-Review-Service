from __future__ import annotations

import json
import subprocess
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path

from arkui_agent.review_service.adapters import CodexAgentRunner, ProcessResult
from arkui_agent.review_service.application import (
    build_agent_output_schema,
    build_diff_review_prompt,
)
from arkui_agent.review_service.domain import AgentReviewRequest, ReviewResultStatus
from arkui_agent.review_service.ports import CodeAgentError


REQUEST = AgentReviewRequest(
    repository="openharmony/arkui_ace_engine",
    pr_id="89521",
    base_sha="3a1b11c2ec8ead1440f6c71e90f7f8bcb9ecbd1a",
    head_sha="040cac089de659ae2b20e37e4f73c7e27b5281bf",
    changed_files=("frameworks/core/common/event_manager.cpp",),
    diff="@@ -10 +10 @@\n-old\n+new",
)


def result_payload(*, findings: list[object] | None = None) -> str:
    return json.dumps(
        {
            "status": "success",
            "repository": REQUEST.repository,
            "pr_id": REQUEST.pr_id,
            "base_sha": REQUEST.base_sha,
            "head_sha": REQUEST.head_sha,
            "findings": [] if findings is None else findings,
        }
    )


class FakeProcessRunner:
    def __init__(self, result: ProcessResult | BaseException) -> None:
        self.result = result
        self.command: tuple[str, ...] | None = None
        self.stdin: str | None = None
        self.schema: Mapping[str, object] | None = None
        self.environment: Mapping[str, str] | None = None

    def run(
        self,
        command: Sequence[str],
        *,
        stdin: str,
        cwd: Path,
        timeout_seconds: float,
        environment: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        self.command = tuple(command)
        self.stdin = stdin
        self.environment = environment
        schema_path = Path(self.command[self.command.index("--output-schema") + 1])
        self.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def runner(process: FakeProcessRunner) -> CodexAgentRunner:
    return CodexAgentRunner(
        prompt_builder=build_diff_review_prompt,
        schema_builder=build_agent_output_schema,
        process_runner=process,
        timeout_seconds=5,
    )


class CodexAgentRunnerTests(unittest.TestCase):
    def test_request_builds_non_interactive_command_prompt_and_schema(self) -> None:
        process = FakeProcessRunner(ProcessResult(0, result_payload(), "progress"))

        result = runner(process).review(REQUEST)

        self.assertEqual(result.status, ReviewResultStatus.SUCCESS)
        self.assertEqual(result.findings, ())
        self.assertEqual(process.command[:2], ("codex", "exec"))
        for argument in (
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--output-schema",
            "-",
        ):
            self.assertIn(argument, process.command)
        self.assertIn(REQUEST.diff, process.stdin or "")
        self.assertNotIn("kb_search", process.stdin or "")
        self.assertNotIn("GITCODE_TOKEN", process.environment or {})
        properties = process.schema["properties"]  # type: ignore[index]
        self.assertEqual(properties["head_sha"]["enum"], [REQUEST.head_sha])

    def test_valid_finding_maps_to_unified_review_result(self) -> None:
        finding = {
            "file": REQUEST.changed_files[0],
            "line": 10,
            "category": "stability",
            "severity": "high",
            "title": "Unchecked state transition",
            "evidence": "the added branch uses new without a guard",
            "explanation": "the diff permits an invalid state",
            "recommendation": "validate the state before applying the change",
            "confidence": 0.9,
        }
        process = FakeProcessRunner(
            ProcessResult(0, result_payload(findings=[finding]), "")
        )

        result = runner(process).review(REQUEST)

        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].file, REQUEST.changed_files[0])
        self.assertEqual(result.findings[0].category, "Stability")
        self.assertEqual(result.findings[0].evidence[0].revision, REQUEST.head_sha)

    def test_nonzero_exit_is_failure(self) -> None:
        process = FakeProcessRunner(ProcessResult(2, "", "private diagnostics"))

        with self.assertRaises(CodeAgentError) as captured:
            runner(process).review(REQUEST)

        self.assertIn("code 2", captured.exception.reason)
        self.assertNotIn("private diagnostics", str(captured.exception))

    def test_timeout_is_failure(self) -> None:
        process = FakeProcessRunner(subprocess.TimeoutExpired("codex", 5))

        with self.assertRaises(CodeAgentError) as captured:
            runner(process).review(REQUEST)

        self.assertIn("timed out", captured.exception.reason)

    def test_process_start_failure_is_failure(self) -> None:
        process = FakeProcessRunner(FileNotFoundError("secret local path"))

        with self.assertRaises(CodeAgentError) as captured:
            runner(process).review(REQUEST)

        self.assertIn("could not start", captured.exception.reason)
        self.assertNotIn("secret local path", captured.exception.reason)

    def test_malformed_json_is_failure(self) -> None:
        process = FakeProcessRunner(ProcessResult(0, "not-json", ""))

        with self.assertRaises(CodeAgentError):
            runner(process).review(REQUEST)

    def test_empty_output_is_failure(self) -> None:
        process = FakeProcessRunner(ProcessResult(0, "  ", ""))

        with self.assertRaises(CodeAgentError) as captured:
            runner(process).review(REQUEST)

        self.assertIn("no output", captured.exception.reason)

    def test_schema_invalid_is_failure(self) -> None:
        payload = json.loads(result_payload())
        payload["unknown"] = True
        process = FakeProcessRunner(ProcessResult(0, json.dumps(payload), ""))

        with self.assertRaises(CodeAgentError):
            runner(process).review(REQUEST)

    def test_identity_mismatch_is_failure(self) -> None:
        payload = json.loads(result_payload())
        payload["head_sha"] = "different"
        process = FakeProcessRunner(ProcessResult(0, json.dumps(payload), ""))

        with self.assertRaises(CodeAgentError) as captured:
            runner(process).review(REQUEST)

        self.assertIn("head_sha", captured.exception.reason)


if __name__ == "__main__":
    unittest.main()
