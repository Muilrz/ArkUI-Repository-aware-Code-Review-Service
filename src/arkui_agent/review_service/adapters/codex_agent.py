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
    ProviderStatus,
    ProviderStatusRef,
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
        timeout_seconds: float = 300.0,
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
            temporary_root = Path(temp_path)
            workdir = (
                Path(request.knowledge.repository_root)
                if request.knowledge is not None
                else temporary_root
            )
            schema_path = temporary_root / "review-result.schema.json"
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
                "--json",
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
        payload, commands = _parse_codex_events(completed.stdout)
        if request.knowledge is not None:
            _validate_knowledge_trace(commands)
        return _parse_agent_result(payload, request)


def _codex_environment() -> dict[str, str]:
    """Inherit CLI authentication while withholding GitCode credentials."""

    return {
        name: value
        for name, value in os.environ.items()
        if name.upper() != "GITCODE_TOKEN"
    }


def _parse_codex_events(payload: str) -> tuple[str, tuple[str, ...]]:
    final_message: str | None = None
    commands: list[str] = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise CodeAgentError("Codex event stream is not valid JSONL") from error
        if not isinstance(event, Mapping):
            raise CodeAgentError("Codex event stream contains a non-object event")
        event_type = event.get("type")
        if event_type in {"error", "turn.failed"}:
            raise CodeAgentError("Codex event stream reported a failed turn")
        item = event.get("item")
        if not isinstance(item, Mapping):
            continue
        if item.get("type") == "command_execution":
            command = item.get("command")
            if isinstance(command, str):
                commands.append(command)
        if (
            event_type == "item.completed"
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            final_message = item["text"]
    if final_message is None or not final_message.strip():
        raise CodeAgentError("Codex event stream has no final agent message")
    return final_message, tuple(commands)


def _validate_knowledge_trace(commands: Sequence[str]) -> None:
    normalized = tuple(command.lower() for command in commands)
    if not any("kb_search.py" in command for command in normalized):
        raise CodeAgentError("Codex did not query Docs KB")
    if not any(
        "git" in command and "rev-parse" in command for command in normalized
    ):
        raise CodeAgentError("Codex did not verify the Live Source revision")
    live_markers = (
        "rg ",
        "rg.exe",
        "git show",
        "get-content",
        "select-string",
        "type ",
        "sed ",
        "awk ",
    )
    if not any(
        any(marker in command for marker in live_markers)
        for command in normalized
    ):
        raise CodeAgentError("Codex did not inspect Live Source")


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
                {
                    "status",
                    "repository",
                    "pr_id",
                    "base_sha",
                    "head_sha",
                    "findings",
                    "degraded",
                    "provider_statuses",
                }
            ),
        )
        _validate_identity(data, request)
        statuses = _parse_provider_statuses(data, request)
        degraded = data["degraded"]
        if not isinstance(degraded, bool):
            raise ValueError("degraded must be a boolean")
        expected_degraded = any(
            status.status is not ProviderStatus.READY for status in statuses
        )
        if degraded != expected_degraded:
            raise ValueError("degraded does not match provider statuses")
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
        degraded=degraded,
        provider_statuses=statuses,
    )


def _parse_provider_statuses(
    data: Mapping[str, object], request: AgentReviewRequest
) -> tuple[ProviderStatusRef, ...]:
    raw = data["provider_statuses"]
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError("provider_statuses must be an array")
    statuses = tuple(ProviderStatusRef.from_dict(item) for item in raw)
    expected = (
        () if request.knowledge is None else request.knowledge.provider_statuses
    )
    if statuses != expected:
        raise ValueError("provider_statuses do not match knowledge preflight")
    return statuses


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
    evidence = _parse_evidence(data["evidence"], request)
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
        evidence=evidence,
        reasoning=explanation,
        suggestion=recommendation,
        confidence=confidence_value(data["confidence"]),
    )


def _parse_evidence(
    value: object, request: AgentReviewRequest
) -> tuple[ProviderEvidenceRef, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("finding evidence must be an array")
    evidence = tuple(ProviderEvidenceRef.from_dict(item) for item in value)
    if not evidence:
        raise ValueError("finding evidence must not be empty")
    if request.knowledge is None:
        if any(
            item.provider != "agent_diff" or item.revision != request.head_sha
            for item in evidence
        ):
            raise ValueError("diff-only evidence must use agent_diff at head_sha")
        return evidence

    status_by_provider = {
        item.provider: item for item in request.knowledge.provider_statuses
    }
    for item in evidence:
        status = status_by_provider.get(item.provider)
        if status is None or status.status is not ProviderStatus.READY:
            raise ValueError("finding evidence must use a ready provider")
        if item.provider in {"live_source", "p1", "p2"}:
            if item.revision != request.head_sha:
                raise ValueError("source evidence revision must match head_sha")
        elif item.provider == "docs_kb" and item.revision != status.revision:
            raise ValueError("Docs KB evidence revision must match provider status")
        if item.provider in {"live_source", "docs_kb"}:
            _validate_evidence_source(item, request)
    if not any(item.provider == "live_source" for item in evidence):
        raise ValueError("repository-aware findings require live_source evidence")
    return evidence


def _validate_evidence_source(
    evidence: ProviderEvidenceRef, request: AgentReviewRequest
) -> None:
    if request.knowledge is None:
        return
    root = Path(request.knowledge.repository_root).resolve()
    candidate = (root / evidence.source).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("evidence source must remain inside repository") from error
    if not candidate.exists():
        raise ValueError("evidence source must exist in target repository")
