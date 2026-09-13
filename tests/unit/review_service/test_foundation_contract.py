from __future__ import annotations

import logging
import unittest

from arkui_agent.review_service.domain import (
    ReviewFailureStage,
    ReviewIdentity,
    ReviewJobFailure,
)
from arkui_agent.review_service.ports import (
    DiagnosticAttribute,
    DiagnosticLevel,
    DiagnosticSink,
    GitCodeProviderError,
    KnowledgeGatewayError,
    ResultStoreError,
    ReviewApplicationError,
    ReviewConfigurationError,
    ReviewConfigurationSource,
    ReviewCorrelation,
    ReviewDiagnostic,
    ReviewEngineError,
    ReviewErrorCategory,
    ReviewServiceConfig,
    SecretValue,
    classify_review_failure,
)


class FakeConfigurationSource:
    def __init__(
        self,
        config: ReviewServiceConfig,
        secrets: dict[str, SecretValue],
    ) -> None:
        self._config = config
        self._secrets = secrets

    def load_service_config(self) -> ReviewServiceConfig:
        return self._config

    def get_secret(self, name: str) -> SecretValue | None:
        return self._secrets.get(name)


class RecordingDiagnosticSink:
    def __init__(self) -> None:
        self.records: list[ReviewDiagnostic] = []

    def emit(self, diagnostic: ReviewDiagnostic) -> None:
        self.records.append(diagnostic)


class ReviewFoundationContractTests(unittest.TestCase):
    def test_public_config_and_secret_loading_paths_are_separate(self) -> None:
        secret = SecretValue("credential-value")
        config = ReviewServiceConfig(review_policy_version=" policy-v1 ")
        source = FakeConfigurationSource(config, {"gitcode": secret})

        self.assertIsInstance(source, ReviewConfigurationSource)
        self.assertEqual(
            source.load_service_config(),
            ReviewServiceConfig(review_policy_version="policy-v1"),
        )
        self.assertIs(source.get_secret("gitcode"), secret)
        self.assertIsNone(source.get_secret("missing"))
        self.assertNotIn("credential-value", repr(config))
        with self.assertRaisesRegex(ValueError, "review_policy_version"):
            ReviewServiceConfig(review_policy_version="  ")
        with self.assertRaisesRegex(ValueError, "secret value"):
            SecretValue("")

    def test_secret_value_is_redacted_in_repr_string_format_and_logs(self) -> None:
        secret_text = "credential-value"
        secret = SecretValue(secret_text)

        self.assertEqual(secret.reveal(), secret_text)
        self.assertEqual(str(secret), "<redacted>")
        self.assertEqual(repr(secret), "SecretValue(<redacted>)")
        self.assertNotIn(secret_text, f"secret={secret!r}")

        with self.assertLogs("review-service-secret-test", level=logging.ERROR) as logs:
            logging.getLogger("review-service-secret-test").error(
                "adapter credential: %s",
                secret,
            )
        self.assertNotIn(secret_text, "\n".join(logs.output))

    def test_diagnostic_redacts_secret_objects_and_sensitive_fields(self) -> None:
        secret_text = "credential-value"
        diagnostic = ReviewDiagnostic(
            correlation=ReviewCorrelation("trace-1", "job-1"),
            level=DiagnosticLevel.WARNING,
            code="review.configuration.warning",
            message="configuration needs attention",
            attributes=(
                DiagnosticAttribute("endpoint", "gitcode.example"),
                DiagnosticAttribute("credential", SecretValue(secret_text)),
                DiagnosticAttribute("access_token", secret_text),
            ),
        )

        self.assertEqual(diagnostic.attributes[0].value, "gitcode.example")
        self.assertEqual(diagnostic.attributes[1].value, "<redacted>")
        self.assertEqual(diagnostic.attributes[2].value, "<redacted>")
        self.assertNotIn(secret_text, repr(diagnostic))
        self.assertNotIn(secret_text, diagnostic.to_json())

    def test_diagnostic_contract_rejects_unsafe_shapes(self) -> None:
        correlation = ReviewCorrelation("trace-1", "job-1")
        with self.assertRaisesRegex(ValueError, "value must be a scalar"):
            DiagnosticAttribute("details", {"nested": "value"})
        with self.assertRaisesRegex(ValueError, "float must be finite"):
            DiagnosticAttribute("duration", float("nan"))
        with self.assertRaisesRegex(ValueError, "unique names"):
            ReviewDiagnostic(
                correlation=correlation,
                level=DiagnosticLevel.INFO,
                code="review.started",
                message="review started",
                attributes=(
                    DiagnosticAttribute("state", "pending"),
                    DiagnosticAttribute("state", "running"),
                ),
            )

    def test_error_taxonomy_covers_domain_application_and_each_port(self) -> None:
        cases = (
            (
                ValueError("invalid domain value"),
                ReviewErrorCategory.VALIDATION,
                "invalid domain value",
            ),
            (
                ReviewConfigurationError("bad public configuration"),
                ReviewErrorCategory.CONFIGURATION,
                "bad public configuration",
            ),
            (
                ReviewApplicationError("application rejected work"),
                ReviewErrorCategory.APPLICATION,
                "application rejected work",
            ),
            (
                GitCodeProviderError("read failed"),
                ReviewErrorCategory.GITCODE_PROVIDER,
                "read failed",
            ),
            (
                KnowledgeGatewayError("provider socket closed"),
                ReviewErrorCategory.KNOWLEDGE_GATEWAY,
                "provider socket closed",
            ),
            (
                ReviewEngineError("review failed"),
                ReviewErrorCategory.REVIEW_ENGINE,
                "review failed",
            ),
            (
                ResultStoreError("save failed"),
                ReviewErrorCategory.RESULT_STORE,
                "save failed",
            ),
            (
                RuntimeError("private detail"),
                ReviewErrorCategory.INTERNAL,
                "private detail",
            ),
        )

        for failure, category, private_reason in cases:
            with self.subTest(failure=type(failure).__name__):
                info = classify_review_failure(failure)
                self.assertEqual(info.category, category)
                self.assertTrue(info.code.startswith("review."))
                self.assertNotIn(private_reason, info.message)

    def test_service_errors_hide_private_reason_from_display_and_logs(self) -> None:
        private_reason = "credential-value"
        failure = KnowledgeGatewayError(private_reason)

        self.assertEqual(failure.reason, private_reason)
        self.assertNotIn(private_reason, str(failure))
        self.assertNotIn(private_reason, repr(failure))
        self.assertNotIn(private_reason, repr(failure.args))
        with self.assertLogs("review-service-error-test", level=logging.ERROR) as logs:
            logging.getLogger("review-service-error-test").error("%r", failure)
        self.assertNotIn(private_reason, "\n".join(logs.output))

    def test_job_failure_classification_reuses_r0_c_failure_model(self) -> None:
        knowledge = ReviewJobFailure(
            stage=ReviewFailureStage.KNOWLEDGE,
            reason="provider detail",
        )
        engine = ReviewJobFailure(
            stage=ReviewFailureStage.ENGINE,
            reason="engine detail",
        )

        self.assertEqual(
            classify_review_failure(knowledge).category,
            ReviewErrorCategory.KNOWLEDGE_GATEWAY,
        )
        self.assertEqual(
            classify_review_failure(engine).category,
            ReviewErrorCategory.REVIEW_ENGINE,
        )
        diagnostic = ReviewDiagnostic.from_failure(
            ReviewCorrelation("trace-1", "job-1"),
            knowledge,
        )
        self.assertEqual(diagnostic.code, "review.job.knowledge_failed")
        self.assertEqual(diagnostic.attributes[1].value, "knowledge")
        self.assertNotIn("provider detail", diagnostic.to_json())

    def test_failure_diagnostic_uses_public_message_not_private_reason(self) -> None:
        private_reason = "credential-value"
        diagnostic = ReviewDiagnostic.from_failure(
            ReviewCorrelation("trace-1", "job-1"),
            KnowledgeGatewayError(private_reason),
        )

        self.assertEqual(diagnostic.code, "review.port.knowledge")
        self.assertEqual(diagnostic.level, DiagnosticLevel.ERROR)
        self.assertNotIn(private_reason, repr(diagnostic))
        self.assertNotIn(private_reason, diagnostic.to_json())

    def test_correlation_and_diagnostic_sink_do_not_change_review_identity(self) -> None:
        identity = ReviewIdentity(
            repository="arkui/ace_engine",
            pr_id="123",
            head_sha="head123",
            review_policy_version="v1",
        )
        identity_before = identity.to_json()
        correlation = ReviewCorrelation("trace-1", "job-1")
        diagnostic = ReviewDiagnostic(
            correlation=correlation,
            level=DiagnosticLevel.INFO,
            code="review.job.started",
            message="review job started",
        )
        sink = RecordingDiagnosticSink()

        self.assertIsInstance(sink, DiagnosticSink)
        sink.emit(diagnostic)
        self.assertEqual(sink.records, [diagnostic])
        self.assertEqual(identity.to_json(), identity_before)
        self.assertNotIn("repository", correlation.to_dict())
        self.assertNotIn("head_sha", correlation.to_dict())


if __name__ == "__main__":
    unittest.main()
