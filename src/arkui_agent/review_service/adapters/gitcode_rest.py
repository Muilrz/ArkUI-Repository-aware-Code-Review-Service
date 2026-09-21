from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..domain import PullRequestContext, PullRequestSummary
from ..domain._validation import non_empty_string
from ..ports import GitCodeProviderError, ReviewConfigurationError, SecretValue


DEFAULT_GITCODE_API_BASE = "https://api.gitcode.com/api/v5"


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes


class HttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> HttpResponse:
        """Execute one HTTP request without interpreting GitCode payloads."""
        ...


class UrllibHttpTransport:
    """Small standard-library transport with sanitized failure reporting."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> HttpResponse:
        request = Request(url=url, data=body, headers=dict(headers), method=method)
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return HttpResponse(status=response.status, body=response.read())
        except HTTPError as error:
            return HttpResponse(status=error.code, body=b"")
        except (URLError, TimeoutError) as error:
            raise GitCodeProviderError(
                f"GitCode network request failed: {type(error).__name__}"
            ) from None


class GitCodeRestAdapter:
    """Minimal GitCode REST adapter for Fast-MVP PR ingestion."""

    def __init__(
        self,
        *,
        repository: str,
        access_token: SecretValue | None = None,
        transport: HttpTransport | None = None,
        api_base: str = DEFAULT_GITCODE_API_BASE,
    ) -> None:
        self._owner, self._repo = _repository_parts(repository)
        self._repository = f"{self._owner}/{self._repo}"
        if access_token is not None and not isinstance(access_token, SecretValue):
            raise ValueError("access_token must be SecretValue or None")
        self._access_token = access_token
        self._transport = transport or UrllibHttpTransport()
        self._api_base = non_empty_string(api_base, field="api_base").rstrip("/")

    @property
    def repository(self) -> str:
        return self._repository

    def list_open_prs(self, *, limit: int = 20) -> tuple[PullRequestSummary, ...]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise ValueError("limit must be an integer between 1 and 100")
        payload = self._request_json(
            "GET",
            self._pulls_path(),
            query={
                "state": "open",
                "sort": "updated",
                "direction": "desc",
                "page": "1",
                "per_page": str(limit),
            },
        )
        if isinstance(payload, (str, bytes)) or not isinstance(payload, Sequence):
            raise GitCodeProviderError("pull request list response must be an array")
        return tuple(self._parse_summary(item) for item in payload)

    def get_pr_context(self, pr_id: str | int) -> PullRequestContext:
        normalized_id = _positive_pr_id(pr_id)
        detail = self._request_json(
            "GET",
            f"{self._pulls_path()}/{normalized_id}",
        )
        detail_data = _mapping(detail, "pull request detail")
        detail_id = _positive_pr_id(
            detail_data.get("number", detail_data.get("iid"))
        )
        if detail_id != normalized_id:
            raise GitCodeProviderError("pull request response id does not match request")
        title = _required_string(detail_data, "title")
        author = _required_nested_string(detail_data, "user", "login")
        base_sha = _required_nested_string(detail_data, "base", "sha")
        head_sha = _required_nested_string(detail_data, "head", "sha")

        files = self._request_json(
            "GET",
            f"{self._pulls_path()}/{normalized_id}/files",
        )
        if isinstance(files, (str, bytes)) or not isinstance(files, Sequence):
            raise GitCodeProviderError("pull request files response must be an array")

        changed_files: list[str] = []
        diff_parts: list[str] = []
        for item in files:
            file_data = _mapping(item, "pull request file")
            patch_data = _optional_mapping(file_data.get("patch"))
            filename = _first_string(
                file_data.get("filename"),
                file_data.get("new_path"),
                patch_data.get("new_path"),
                field="changed file path",
            )
            old_path = _first_string(
                file_data.get("old_path"),
                patch_data.get("old_path"),
                filename,
                field="old file path",
            )
            fragment = _first_diff(
                patch_data.get("diff"),
                file_data.get("diff"),
            )
            changed_files.append(filename)
            diff_parts.append(f"diff --git a/{old_path} b/{filename}\n{fragment}")

        return PullRequestContext(
            repository=self._repository,
            pr_id=detail_id,
            title=title,
            author=author,
            base_sha=base_sha,
            head_sha=head_sha,
            changed_files=tuple(changed_files),
            diff="\n".join(diff_parts),
        )

    def post_summary_comment(self, pr_id: str | int, body: str) -> str:
        normalized_id = _positive_pr_id(pr_id)
        comment_body = non_empty_string(body, field="comment body")
        if self._access_token is None:
            raise ReviewConfigurationError(
                "GITCODE_TOKEN is required to post a pull request comment"
            )
        payload = self._request_json(
            "POST",
            f"{self._pulls_path()}/{normalized_id}/comments",
            body={"body": comment_body},
        )
        data = _mapping(payload, "pull request comment")
        return _first_string(data.get("id"), field="comment id")

    def _parse_summary(self, value: object) -> PullRequestSummary:
        data = _mapping(value, "pull request list item")
        diff_refs = _optional_mapping(data.get("diff_refs"))
        base = _optional_mapping(data.get("base"))
        head = _optional_mapping(data.get("head"))
        return PullRequestSummary(
            repository=self._repository,
            pr_id=_positive_pr_id(data.get("number", data.get("iid"))),
            title=_required_string(data, "title"),
            author=_required_nested_string(data, "user", "login"),
            base_sha=_first_string(
                diff_refs.get("base_sha"), base.get("sha"), field="base SHA"
            ),
            head_sha=_first_string(
                diff_refs.get("head_sha"), head.get("sha"), field="head SHA"
            ),
        )

    def _pulls_path(self) -> str:
        return f"/repos/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}/pulls"

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> object:
        params = dict(query or {})
        if self._access_token is not None:
            params["access_token"] = self._access_token.reveal()
        url = f"{self._api_base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        encoded_body = None
        headers = {"Accept": "application/json"}
        if body is not None:
            encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        response = self._transport.request(
            method=method,
            url=url,
            headers=headers,
            body=encoded_body,
        )
        if not 200 <= response.status < 300:
            raise GitCodeProviderError(
                f"GitCode returned unexpected HTTP status {response.status}"
            )
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GitCodeProviderError("GitCode returned invalid JSON") from error


def _repository_parts(repository: object) -> tuple[str, str]:
    normalized = non_empty_string(repository, field="repository")
    parts = normalized.split("/")
    if len(parts) != 2 or any(not part.strip() for part in parts):
        raise ValueError("repository must use owner/repo format")
    return parts[0].strip(), parts[1].strip()


def _positive_pr_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise GitCodeProviderError("pull request id is missing or invalid")
    normalized = str(value).strip()
    if not normalized.isdigit() or int(normalized) <= 0:
        raise GitCodeProviderError("pull request id is missing or invalid")
    return normalized


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise GitCodeProviderError(f"{label} must be an object")
    return value


def _optional_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _required_string(data: Mapping[str, object], field: str) -> str:
    return _first_string(data.get(field), field=field)


def _required_nested_string(
    data: Mapping[str, object], outer: str, inner: str
) -> str:
    nested = _mapping(data.get(outer), outer)
    return _first_string(nested.get(inner), field=f"{outer}.{inner}")


def _first_string(*values: object, field: str) -> str:
    for value in values:
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            normalized = str(value).strip()
            if normalized:
                return normalized
    raise GitCodeProviderError(f"{field} is missing or invalid")


def _first_diff(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    raise GitCodeProviderError("file diff is missing or invalid")
