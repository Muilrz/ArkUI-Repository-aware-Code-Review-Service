from __future__ import annotations

from ..domain import ProviderEvidenceRef, ReviewFinding, ReviewResult
from ..ports.publishing import SummaryCommentPublisher


def format_review_summary(result: ReviewResult) -> str:
    """Format a validated review result as a concise GitCode Markdown comment."""

    if not isinstance(result, ReviewResult):
        raise ValueError("result must be ReviewResult")

    lines = [
        "# ArkUI Automated Code Review",
        "",
        f"Review completed successfully for head `{result.head_sha}`.",
        "",
        "## Knowledge status",
        "",
        f"- degraded: `{str(result.degraded).lower()}`",
    ]
    if result.provider_statuses:
        lines.extend(
            f"- {status.provider}: `{status.status.value}`"
            + (f" (revision `{status.revision}`)" if status.revision else "")
            for status in result.provider_statuses
        )
    else:
        lines.append("- provider status: not supplied (diff-only review)")

    lines.extend(("", "## Findings", ""))
    if not result.findings:
        lines.extend(
            (
                "No issues with sufficient evidence were found.",
                "",
                "This means the review completed successfully; it does not guarantee "
                "that the code is defect-free.",
            )
        )
    else:
        for index, finding in enumerate(result.findings, start=1):
            lines.extend(_format_finding(index, finding))

    lines.extend(
        (
            "",
            "---",
            f"Repository: `{result.repository}` · PR: `{result.pr_id}` · "
            f"Base: `{result.base_sha}` · Head: `{result.head_sha}`",
        )
    )
    return "\n".join(lines)


class ReviewPublishingService:
    """Application service that formats and publishes a validated result."""

    def __init__(self, publisher: SummaryCommentPublisher) -> None:
        if not isinstance(publisher, SummaryCommentPublisher):
            raise ValueError("publisher must implement SummaryCommentPublisher")
        self._publisher = publisher

    def publish(self, result: ReviewResult) -> str:
        body = format_review_summary(result)
        return self._publisher.post_summary_comment(result.pr_id, body)


def _format_finding(index: int, finding: ReviewFinding) -> tuple[str, ...]:
    location = _format_location(finding)
    lines = [
        f"### {index}. [{finding.severity.value}] {finding.title}",
        "",
        f"- Category: {finding.category}",
        f"- Location: `{finding.file}:{location}`",
        f"- Explanation: {finding.description}",
        f"- Evidence: {_format_evidence(finding.evidence)}",
        f"- Recommendation: {finding.suggestion}",
        "",
    ]
    return tuple(lines)


def _format_location(finding: ReviewFinding) -> str:
    start = finding.location.start_line
    end = finding.location.end_line
    return f"L{start}" if start == end else f"L{start}-L{end}"


def _format_evidence(evidence: tuple[ProviderEvidenceRef, ...]) -> str:
    rendered: list[str] = []
    for item in evidence:
        locator = f":{item.locator}" if item.locator else ""
        revision = f" @ {item.revision}" if item.revision else ""
        rendered.append(
            f"`{item.provider}: {item.source}{locator}{revision}`"
        )
    return "; ".join(rendered)
