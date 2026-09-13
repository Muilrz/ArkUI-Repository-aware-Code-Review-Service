# R0 Foundation Traceability

## Scope

本文将 [Phase Map 的 R0 Definition of Done](../../exec-plans/phase-map.md#definition-of-done) 映射到已经实现的 spec、implementation 和 tests。它只证明 R0 foundation contract，不把 R1+ 能力声明为已实现。

## Definition of Done evidence

| R0 DoD | Specification evidence | Implementation evidence | Test evidence |
| --- | --- | --- | --- |
| 1. Domain 不引用 GitCode schema、MCP transport 或具体 storage | [Package Boundaries](package-boundaries.md) | [`review_service/domain`](../../../src/arkui_agent/review_service/domain/) | [`test_package_boundaries.py`](../../../tests/unit/review_service/test_package_boundaries.py) |
| 2. ReviewIdentity 四字段、确定 serialization/equality | [Core Domain Models — ReviewIdentity](core-domain-models.md#reviewidentity) | [`identity.py`](../../../src/arkui_agent/review_service/domain/identity.py) | [`test_domain_models.py`](../../../tests/unit/review_service/test_domain_models.py) |
| 3. ReviewFinding 必填字段与四级 severity | [Core Domain Models — ReviewFinding](core-domain-models.md#reviewfinding) | [`finding.py`](../../../src/arkui_agent/review_service/domain/finding.py) | [`test_domain_models.py`](../../../tests/unit/review_service/test_domain_models.py) |
| 4. Job/result/knowledge/engine ports、依赖方向和失败类型固定 | [Application Ports and Job Lifecycle](application-ports-and-job-lifecycle.md)、[Foundation Errors](foundation-configuration-errors-observability.md#error-taxonomy) | [`job.py`](../../../src/arkui_agent/review_service/domain/job.py)、[`ports`](../../../src/arkui_agent/review_service/ports/) | [`test_application_contract.py`](../../../tests/unit/review_service/test_application_contract.py)、[`test_foundation_contract.py`](../../../tests/unit/review_service/test_foundation_contract.py)、[`test_package_boundaries.py`](../../../tests/unit/review_service/test_package_boundaries.py) |
| 5. Test doubles 走通无真实 GitCode/knowledge/reasoning 的 orchestration | [Application Ports and Job Lifecycle — Test doubles](application-ports-and-job-lifecycle.md#test-doubles) | [`job_manager.py`](../../../src/arkui_agent/review_service/application/job_manager.py)、[`review_service.py` fixtures](../../../tests/fixtures/review_service.py) | [`test_application_contract.py`](../../../tests/unit/review_service/test_application_contract.py) |
| 6. Configuration 与 trace/correlation 不承载 secrets 或平台逻辑 | [Foundation Configuration, Errors and Observability](foundation-configuration-errors-observability.md) | [`configuration.py`](../../../src/arkui_agent/review_service/ports/configuration.py)、[`diagnostics.py`](../../../src/arkui_agent/review_service/ports/diagnostics.py) | [`test_foundation_contract.py`](../../../tests/unit/review_service/test_foundation_contract.py) |
| 7. Tests 与 Acceptance Criteria 通过后完成计划 | [Completed R0 execution plan](../../exec-plans/completed/R0-review-service-foundation.md) | R0-A～D scope 内文件 | 上述 R0 contract tests；targeted validation 结果记录于 completed plan |

## Explicitly absent

R0 没有 concrete GitCode/config/secret/diagnostic adapter，没有 durable state/dedup/retry/backoff，没有 Repository Knowledge provider、Review Engine reasoning、scheduler、MCP 或 Skill。以上能力必须由 R1–R5 独立计划与验收。
