from __future__ import annotations

import json
import unittest

from arkui_agent.review_service.domain import (
    ChangeRef,
    ProviderEvidenceRef,
    ProviderStatus,
    ProviderStatusRef,
    ReviewFinding,
    ReviewIdentity,
    ReviewRequest,
    ReviewResultSummary,
    ReviewSeverity,
    SourceRange,
)


class ReviewDomainModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = ReviewIdentity(
            repository="arkui/ace_engine",
            pr_id="123",
            head_sha="abc123",
            review_policy_version="v1",
        )
        self.source_range = SourceRange(
            start_line=10,
            end_line=12,
            start_column=2,
            end_column=8,
        )
        self.evidence = ProviderEvidenceRef(
            provider="live_source",
            revision="abc123",
            source="frameworks/core/example.cpp",
            locator="10:2-12:8",
        )

    def test_review_identity_has_stable_value_equality_and_canonical_json(self) -> None:
        same = ReviewIdentity.from_json(self.identity.to_json())

        self.assertEqual(same, self.identity)
        self.assertEqual(hash(same), hash(self.identity))
        self.assertEqual(
            self.identity.to_json(),
            '{"head_sha":"abc123","pr_id":"123",'
            '"repository":"arkui/ace_engine","review_policy_version":"v1"}',
        )

    def test_review_identity_rejects_missing_unknown_and_empty_fields(self) -> None:
        valid = self.identity.to_dict()
        for invalid in (
            {key: value for key, value in valid.items() if key != "head_sha"},
            {**valid, "platform": "gitcode"},
            {**valid, "repository": " "},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ReviewIdentity.from_dict(invalid)

    def test_source_range_validates_line_and_column_order(self) -> None:
        for invalid in (
            {"start_line": 0, "end_line": 1},
            {"start_line": 5, "end_line": 4},
            {
                "start_line": 5,
                "end_line": 5,
                "start_column": 9,
                "end_column": 8,
            },
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                SourceRange(**invalid)

        self.assertEqual(
            SourceRange.from_json(self.source_range.to_json()),
            self.source_range,
        )

    def test_review_request_round_trips_diff_and_dual_side_change_refs(self) -> None:
        request = ReviewRequest(
            identity=self.identity,
            base_sha="base123",
            diff="@@ -10,2 +10,3 @@",
            changed_files=("frameworks/core/example.cpp",),
            changes=(
                ChangeRef(
                    file="frameworks/core/example.cpp",
                    old_range=SourceRange(10, 11),
                    new_range=SourceRange(10, 12),
                ),
            ),
        )

        self.assertEqual(ReviewRequest.from_json(request.to_json()), request)
        self.assertEqual(json.loads(request.to_json())["identity"], self.identity.to_dict())

    def test_review_request_rejects_unlisted_change_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "must belong to changed_files"):
            ReviewRequest(
                identity=self.identity,
                base_sha="base123",
                diff="diff",
                changed_files=("a.cpp",),
                changes=(ChangeRef("b.cpp", new_range=SourceRange(1, 1)),),
            )

        with self.assertRaisesRegex(ValueError, "must not contain duplicates"):
            ReviewRequest(
                identity=self.identity,
                base_sha="base123",
                diff="diff",
                changed_files=("a.cpp", "a.cpp"),
                changes=(ChangeRef("a.cpp", new_range=SourceRange(1, 1)),),
            )

    def test_canonical_collections_reject_unordered_inputs(self) -> None:
        change = ChangeRef("a.cpp", new_range=SourceRange(1, 1))
        with self.assertRaisesRegex(ValueError, "changed_files must be a sequence"):
            ReviewRequest(
                identity=self.identity,
                base_sha="base123",
                diff="diff",
                changed_files={"a.cpp"},
                changes=(change,),
            )
        with self.assertRaisesRegex(ValueError, "changes must be a sequence"):
            ReviewRequest(
                identity=self.identity,
                base_sha="base123",
                diff="diff",
                changed_files=("a.cpp",),
                changes={change},
            )

    def test_change_and_provider_refs_have_direct_canonical_round_trips(self) -> None:
        change = ChangeRef(
            file="frameworks/core/example.cpp",
            new_range=self.source_range,
        )
        status = ProviderStatusRef(
            provider="live_source",
            status=ProviderStatus.READY,
            revision="abc123",
        )

        self.assertEqual(ChangeRef.from_json(change.to_json()), change)
        self.assertEqual(
            ProviderEvidenceRef.from_json(self.evidence.to_json()),
            self.evidence,
        )
        self.assertEqual(ProviderStatusRef.from_json(status.to_json()), status)

    def test_public_deserializers_reject_unknown_fields(self) -> None:
        change = ChangeRef(
            file="frameworks/core/example.cpp",
            new_range=self.source_range,
        )
        status = ProviderStatusRef(
            provider="live_source",
            status=ProviderStatus.READY,
            revision="abc123",
        )
        values = (
            (SourceRange.from_dict, self.source_range.to_dict()),
            (ChangeRef.from_dict, change.to_dict()),
            (ProviderEvidenceRef.from_dict, self.evidence.to_dict()),
            (ProviderStatusRef.from_dict, status.to_dict()),
        )

        for loader, value in values:
            invalid = {**value, "unexpected": True}
            with self.subTest(loader=loader.__qualname__), self.assertRaisesRegex(
                ValueError, "unknown fields"
            ):
                loader(invalid)

    def test_provider_status_uses_fixed_vocabulary_and_preserves_diagnostics(self) -> None:
        status = ProviderStatusRef(
            provider="p1",
            status=ProviderStatus.STALE,
            revision="old123",
            version="p1-v1",
            diagnostics=("target revision is abc123",),
        )

        self.assertEqual(ProviderStatusRef.from_dict(status.to_dict()), status)
        self.assertEqual(status.to_dict()["status"], "stale")
        with self.assertRaisesRegex(ValueError, "unknown provider status"):
            ProviderStatusRef(provider="p1", status="maybe")

    def test_review_finding_round_trips_all_required_fields(self) -> None:
        finding = ReviewFinding(
            file="frameworks/core/example.cpp",
            location=self.source_range,
            category="Stability",
            severity=ReviewSeverity.HIGH,
            title="Guard the nullable callback",
            description="The changed branch invokes an optional callback.",
            evidence=(self.evidence,),
            reasoning="Live source shows no null check on the changed path.",
            suggestion="Check the callback before invoking it.",
            confidence=0.9,
        )

        self.assertEqual(ReviewFinding.from_json(finding.to_json()), finding)
        self.assertEqual(finding.to_dict()["severity"], "High")

    def test_review_finding_rejects_bad_severity_confidence_and_empty_evidence(self) -> None:
        base = {
            "file": "a.cpp",
            "location": self.source_range,
            "category": "Stability",
            "severity": ReviewSeverity.LOW,
            "title": "title",
            "description": "description",
            "evidence": (self.evidence,),
            "reasoning": "reasoning",
            "suggestion": "suggestion",
            "confidence": 0.5,
        }
        for updates in (
            {"severity": "Informational"},
            {"confidence": 1.1},
            {"evidence": ()},
            {"evidence": {self.evidence}},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                ReviewFinding(**{**base, **updates})

    def test_nested_unknown_fields_are_rejected(self) -> None:
        finding = ReviewFinding(
            file="a.cpp",
            location=SourceRange(1, 1),
            category="Functional Correctness",
            severity=ReviewSeverity.MEDIUM,
            title="title",
            description="description",
            evidence=(self.evidence,),
            reasoning="reasoning",
            suggestion="suggestion",
            confidence=0.5,
        ).to_dict()
        finding["evidence"][0]["unsupported"] = True

        with self.assertRaisesRegex(ValueError, "unknown fields"):
            ReviewFinding.from_dict(finding)

    def test_result_summary_requires_degradation_for_non_ready_provider(self) -> None:
        stale = ProviderStatusRef(
            provider="p2",
            status=ProviderStatus.STALE,
            revision="old123",
        )
        with self.assertRaisesRegex(ValueError, "degraded must be true"):
            ReviewResultSummary(
                identity=self.identity,
                finding_count=0,
                degraded=False,
                provider_statuses=(stale,),
            )

        summary = ReviewResultSummary(
            identity=self.identity,
            finding_count=0,
            degraded=True,
            provider_statuses=(stale,),
        )
        self.assertEqual(ReviewResultSummary.from_json(summary.to_json()), summary)

    def test_result_summary_rejects_duplicate_provider_names(self) -> None:
        ready = ProviderStatusRef(provider="live_source", status=ProviderStatus.READY)
        with self.assertRaisesRegex(ValueError, "unique provider names"):
            ReviewResultSummary(
                identity=self.identity,
                finding_count=0,
                degraded=False,
                provider_statuses=(ready, ready),
            )


if __name__ == "__main__":
    unittest.main()
