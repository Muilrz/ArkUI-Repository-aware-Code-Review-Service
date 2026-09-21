from __future__ import annotations

import json
import unittest
from collections.abc import Mapping
from dataclasses import dataclass

from arkui_agent.review_service.adapters import (
    GitCodeRestAdapter,
    HttpResponse,
)
from arkui_agent.review_service.domain import (
    PullRequestContext,
    PullRequestSummary,
)
from arkui_agent.review_service.ports import (
    GitCodeProviderError,
    ReviewConfigurationError,
    SecretValue,
)


REPOSITORY = "openharmony/arkui_ace_engine"
PR_ID = 89521
BASE_SHA = "3a1b11c2ec8ead1440f6c71e90f7f8bcb9ecbd1a"
HEAD_SHA = "040cac089de659ae2b20e37e4f73c7e27b5281bf"


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None


class FakeHttpTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[RecordedRequest] = []

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> HttpResponse:
        self.requests.append(RecordedRequest(method, url, headers, body))
        if not self._responses:
            raise AssertionError("unexpected HTTP request")
        return self._responses.pop(0)


def json_response(value: object, *, status: int = 200) -> HttpResponse:
    return HttpResponse(
        status=status,
        body=json.dumps(value, ensure_ascii=False).encode("utf-8"),
    )


def pr_detail() -> dict[str, object]:
    return {
        "number": PR_ID,
        "title": "fix gesture arbitration",
        "user": {"login": "hct95"},
        "base": {"sha": BASE_SHA},
        "head": {"sha": HEAD_SHA},
    }


def pr_files() -> list[dict[str, object]]:
    return [
        {
            "filename": "frameworks/core/common/event_manager.cpp",
            "patch": {
                "old_path": "frameworks/core/common/event_manager.cpp",
                "new_path": "frameworks/core/common/event_manager.cpp",
                "diff": "@@ -10 +10 @@\n-old\n+new",
            },
        },
        {
            "filename": "frameworks/core/gestures/recognizer.cpp",
            "diff": "@@ -20 +20 @@\n-before\n+after",
        },
    ]


class GitCodeRestAdapterTests(unittest.TestCase):
    def test_pr_responses_map_to_revision_bound_context(self) -> None:
        transport = FakeHttpTransport(
            [json_response(pr_detail()), json_response(pr_files())]
        )
        adapter = GitCodeRestAdapter(repository=REPOSITORY, transport=transport)

        context = adapter.get_pr_context(PR_ID)

        self.assertIsInstance(context, PullRequestContext)
        self.assertEqual(context.repository, REPOSITORY)
        self.assertEqual(context.pr_id, str(PR_ID))
        self.assertEqual(context.author, "hct95")
        self.assertEqual(context.base_sha, BASE_SHA)
        self.assertEqual(context.head_sha, HEAD_SHA)
        self.assertEqual(
            context.changed_files,
            (
                "frameworks/core/common/event_manager.cpp",
                "frameworks/core/gestures/recognizer.cpp",
            ),
        )
        self.assertIn("diff --git a/frameworks/core/common/event_manager.cpp", context.diff)
        self.assertIn("@@ -20 +20 @@", context.diff)
        self.assertEqual([request.method for request in transport.requests], ["GET", "GET"])
        self.assertTrue(transport.requests[0].url.endswith(f"/pulls/{PR_ID}"))
        self.assertTrue(transport.requests[1].url.endswith(f"/pulls/{PR_ID}/files"))

    def test_list_open_prs_maps_documented_diff_refs(self) -> None:
        transport = FakeHttpTransport(
            [
                json_response(
                    [
                        {
                            "iid": PR_ID,
                            "title": "fix gesture arbitration",
                            "user": {"login": "hct95"},
                            "diff_refs": {
                                "base_sha": BASE_SHA,
                                "head_sha": HEAD_SHA,
                            },
                        }
                    ]
                )
            ]
        )
        adapter = GitCodeRestAdapter(repository=REPOSITORY, transport=transport)

        summaries = adapter.list_open_prs(limit=5)

        self.assertEqual(
            summaries,
            (
                PullRequestSummary(
                    repository=REPOSITORY,
                    pr_id=str(PR_ID),
                    title="fix gesture arbitration",
                    author="hct95",
                    base_sha=BASE_SHA,
                    head_sha=HEAD_SHA,
                ),
            ),
        )
        self.assertIn("state=open", transport.requests[0].url)
        self.assertIn("per_page=5", transport.requests[0].url)

    def test_malformed_required_sha_fails_without_fake_context(self) -> None:
        malformed = pr_detail()
        malformed["head"] = {}
        adapter = GitCodeRestAdapter(
            repository=REPOSITORY,
            transport=FakeHttpTransport([json_response(malformed)]),
        )

        with self.assertRaises(GitCodeProviderError) as raised:
            adapter.get_pr_context(PR_ID)

        self.assertIn("head.sha", raised.exception.reason)

    def test_http_failure_is_explicit_and_does_not_leak_secret(self) -> None:
        secret_text = "private-token-value"
        adapter = GitCodeRestAdapter(
            repository=REPOSITORY,
            access_token=SecretValue(secret_text),
            transport=FakeHttpTransport(
                [HttpResponse(status=401, body=secret_text.encode("utf-8"))]
            ),
        )

        with self.assertRaises(GitCodeProviderError) as raised:
            adapter.list_open_prs()

        self.assertIn("401", raised.exception.reason)
        self.assertNotIn(secret_text, raised.exception.reason)
        self.assertNotIn(secret_text, str(raised.exception))
        self.assertNotIn(secret_text, repr(raised.exception))
        self.assertNotIn(secret_text, repr(adapter))

    def test_comment_write_boundary_posts_summary_body(self) -> None:
        transport = FakeHttpTransport([json_response({"id": "comment-1"})])
        adapter = GitCodeRestAdapter(
            repository=REPOSITORY,
            access_token=SecretValue("private-token-value"),
            transport=transport,
        )

        comment_id = adapter.post_summary_comment(PR_ID, "review summary")

        self.assertEqual(comment_id, "comment-1")
        request = transport.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertIn(f"/pulls/{PR_ID}/comments", request.url)
        self.assertEqual(
            json.loads(request.body.decode("utf-8")),
            {"body": "review summary"},
        )
        self.assertEqual(request.headers["Content-Type"], "application/json")

    def test_comment_boundary_requires_token_before_http(self) -> None:
        transport = FakeHttpTransport([])
        adapter = GitCodeRestAdapter(repository=REPOSITORY, transport=transport)

        with self.assertRaises(ReviewConfigurationError):
            adapter.post_summary_comment(PR_ID, "review summary")

        self.assertEqual(transport.requests, [])

    def test_comment_http_failure_is_explicit_and_redacts_secret(self) -> None:
        secret = "private-token-value"
        adapter = GitCodeRestAdapter(
            repository=REPOSITORY,
            access_token=SecretValue(secret),
            transport=FakeHttpTransport(
                [HttpResponse(status=403, body=secret.encode("utf-8"))]
            ),
        )

        with self.assertRaises(GitCodeProviderError) as raised:
            adapter.post_summary_comment(PR_ID, "review summary")

        self.assertIn("403", raised.exception.reason)
        self.assertNotIn(secret, raised.exception.reason)
        self.assertNotIn(secret, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
