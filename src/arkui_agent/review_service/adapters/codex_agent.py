from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from ..domain import (
    AgentReviewRequest,
    ProviderEvidenceRef,
    ReviewFinding,
    ReviewResult,
    ReviewResultStatus,
    ReviewSeverity,
    SourceRange,
)
from ..domain._validation import confidence_value, non_empty_string, strict_mapping
from ..ports import CodeAgentError
from .process import ProcessRunner, SubprocessRunner


PromptBuilder = Callable[[AgentReviewRequest], str]
SchemaBuilder = Callable[[AgentReviewRequest], Mapping[str, object]]

_CATEGORY_NAMES = {
    "stability": "Stability",
    "memory_resource_lifetime": "Memory / Resource / Lifetime",
    "functional_correctness": "Functional Correctness",
}
_SEVERITIES = {
    "critical": ReviewSeverity.CRITICAL,
    "high": ReviewSeverity.HIGH,
    "medium": ReviewSeverity.MEDIUM,
    "low": ReviewSeverity.LOW,
}
_FINDING_FIELDS = frozenset(
    {
        "file",
        "line",
        "category",
        "severity",
        "title",
        "evidence",
        "explanation",
        "recommendation",
        "confidence",
    }
)


class CodexAgentRunner:
    """Codex CLI backend for the platform-neutral CodeAgentRunner port."""

    def __init__(
        self,
        *,
        prompt_builder: PromptBuilder,
        schema_builder: SchemaBuilder,
        process_runner: ProcessRunner | None = None,
        executable: str = "codex",
        timeout_seconds: float = 180.0,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._schema_builder = schema_builder
        self._process_runner = process_runner or SubprocessRunner()
        self._executable = non_empty_string(executable, field="executable")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds

    def review(self, request: AgentReviewRequest) -> ReviewResult:
        if not isinstance(request, AgentReviewRequest):
            raise ValueError("request must be AgentReviewRequest")
        prompt = self._prompt_builder(request)
        schema = self._schema_builder(request)

        with tempfile.TemporaryDirectory(prefix="arkui-review-agent-") as temp_path:
            workdir = Path(temp_path)
            schema_path = workdir / "review-result.schema.json"
            schema_path.write_text(
                json.dumps(schema, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            command = (
                self._executable,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_path),
                "-",
            )
            try:
                completed = self._process_runner.run(
                    command,
                    stdin=prompt,
                    cwd=workdir,
                    timeout_seconds=self._timeout_seconds,
                    environment=_codex_environment(),
                )
            except subprocess.TimeoutExpired as error:
                raise CodeAgentError("Codex process timed out") from None
            except OSError as error:
                raise CodeAgentError(
                    f"Codex process could not start: {type(error).__name__}"
                ) from None

        if completed.exit_code != 0:
            raise CodeAgentError(
                f"Codex process exited with code {completed.exit_code}"
            )
        if not completed.stdout.strip():
            raise CodeAgentError("Codex process returned no output")
        return _parse_agent_result(completed.stdout, request)


def _codex_environment() -> dict[str, str]:
    """Inherit CLI authentication while withholding GitCode credentials."""

    return {
        name: value
        for name, value in os.environ.items()
        if name.upper() != "GITCODE_TOKEN"
    }


def _parse_agent_result(payload: str, request: AgentReviewRequest) -> ReviewResult:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise CodeAgentError("Codex output is not valid JSON") from error
    try:
        data = strict_mapping(
            value,
            type_name="AgentReviewResult",
            required=frozenset(
                {"status", "repository", "pr_id", "base_sha", "head_sha", "findings"}
            ),
        )
        _validate_identity(data, request)
        raw_findings = data["findings"]
        if isinstance(raw_findings, (str, bytes)) or not isinstance(
            raw_findings, Sequence
        ):
            raise ValueError("findings must be an array")
        findings = tuple(_parse_finding(item, request) for item in raw_findings)
    except (TypeError, ValueError) as error:
        raise CodeAgentError(f"Codex output schema is invalid: {error}") from error
    return ReviewResult(
        status=ReviewResultStatus.SUCCESS,
        repository=request.repository,
        pr_id=request.pr_id,
        base_sha=request.base_sha,
        head_sha=request.head_sha,
        findings=findings,
    )


def _validate_identity(
    data: Mapping[str, object], request: AgentReviewRequest
) -> None:
    expected = {
        "status": "success",
        "repository": request.repository,
        "pr_id": request.pr_id,
        "base_sha": request.base_sha,
        "head_sha": request.head_sha,
    }
    for field, value in expected.items():
        if data[field] != value:
            raise ValueError(f"{field} does not match the review request")


def _parse_finding(value: object, request: AgentReviewRequest) -> ReviewFinding:
    data = strict_mapping(
        value,
        type_name="AgentReviewFinding",
        required=_FINDING_FIELDS,
    )
    file = non_empty_string(data["file"], field="file")
    if file not in request.changed_files:
        raise ValueError("finding file must belong to changed_files")
    line = data["line"]
    if isinstance(line, bool) or not isinstance(line, int) or line < 1:
        raise ValueError("finding line must be a positive integer")
    category_key = data["category"]
    if category_key not in _CATEGORY_NAMES:
        raise ValueError("finding category is unsupported")
    severity_key = data["severity"]
    if severity_key not in _SEVERITIES:
        raise ValueError("finding severity is unsupported")
    evidence_text = non_empty_string(data["evidence"], field="evidence")
    explanation = non_empty_string(data["explanation"], field="explanation")
    recommendation = non_empty_string(
        data["recommendation"], field="recommendation"
    )
    return ReviewFinding(
        file=file,
        location=SourceRange(line, line),
        category=_CATEGORY_NAMES[category_key],
        severity=_SEVERITIES[severity_key],
        title=non_empty_string(data["title"], field="title"),
        description=explanation,
        evidence=(
            ProviderEvidenceRef(
                provider="agent_diff",
                revision=request.head_sha,
                source=file,
                locator=f"line {line}: {evidence_text}",
            ),
        ),
        reasoning=explanation,
        suggestion=recommendation,
        confidence=confidence_value(data["confidence"]),
    )
