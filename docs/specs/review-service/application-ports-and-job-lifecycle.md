# Application Ports and Job Lifecycle

## Scope

本文定义 R0-C 已实现的四个 structural ports、最小同步 job lifecycle 和 application orchestration。所有 request、identity、finding、provider evidence/status 与 result summary 直接复用 [R0-B core domain models](core-domain-models.md)，不建立 application-layer duplicate models。

R0-C 没有实现 GitCode HTTP、Repository Knowledge provider、review reasoning、durable database、dedup、retry/timeout/cancel、background loop、MCP 或 configuration/observability。

## Ports

### GitCodeProvider

```text
load_review(ReviewIdentity) -> ReviewRequest
```

输入与输出均为 R0-B model。失败使用 `GitCodeProviderError`。R0-C 只定义 port，不在 Job Manager 中主动加载 PR；normalized request 是当前 application entry point。R0-D 起 error 的 `str`/`repr` 使用无私有 detail 的公开 message，内部 detail 仅由显式 `.reason` 读取。

### KnowledgeGateway

```text
collect(ReviewRequest) -> KnowledgeBundle
```

`KnowledgeBundle` 只聚合 R0-B `ProviderEvidenceRef` 与 `ProviderStatusRef`。它不是 R3 的 ranked/budgeted `ReviewContextPack`，不实现 freshness 或 provider selection policy。失败使用 `KnowledgeGatewayError`。

### ReviewEngine

```text
review(ReviewRequest, KnowledgeBundle) -> tuple[ReviewFinding, ...]
```

Finding 直接使用 R0-B model；zero findings 是合法成功。R0-C 不实现真实 reasoning、category policy 或 output validation。失败使用 `ReviewEngineError`。

### ResultStore

```text
save(ReviewJobRecord) -> None
get(ReviewIdentity) -> ReviewJobRecord | None
```

R0-C 只定义 latest-record port。持久化、transaction、并发 claim、dedup、retry/restart 和 history retention 属于后续阶段。失败使用 `ResultStoreError`。

四个 ports 都是 `runtime_checkable Protocol`；所有 expected port error 都要求非空 reason，并由 R0-D [error taxonomy](foundation-configuration-errors-observability.md#error-taxonomy) 提供稳定公开分类；concrete adapters 位于后续 milestone。

## Job model

`ReviewJobState` 只包含：

```text
pending
running
succeeded
failed
```

允许的最小执行路径：

```text
PENDING -> RUNNING -> SUCCEEDED
                   -> FAILED
```

- pending/running 不含 findings、summary 或 failure；
- succeeded 必须有 identity/count 一致的 R0-B `ReviewResultSummary`，可以有 zero findings，不能有 failure；
- failed 必须有 `ReviewJobFailure`，不能保存 findings 或 success summary；
- R0-C failure stage 只区分 `knowledge` 与 `engine`。R0-D taxonomy 映射这两个既有 stage，不替换 `ReviewJobFailure`。

## ReviewJobManager

`execute(ReviewRequest)` 依次：

1. 保存 pending；
2. 保存 running；
3. 调用 KnowledgeGateway；
4. 调用 ReviewEngine；
5. 从 findings 和 provider statuses 构建 R0-B summary；
6. 保存并返回 succeeded。

`KnowledgeGatewayError` 或 `ReviewEngineError` 被转换为相应 failed record 并保存；R0-D 起保存的是 taxonomy 固定的公开 message，不复制 port 的私有 reason。ResultStoreError 和未声明异常向调用者传播，不能被伪装为 failed persistence 或 success。R0-C 不包含 retry、timeout、cancel、dedup、async queue 或 background execution。

## Test doubles

`tests/fixtures/review_service.py` 提供 FakeGitCodeProvider、FakeKnowledgeGateway、FakeReviewEngine 和 InMemoryResultStore，仅用于 contract tests，不是 production adapters。Contract tests 固定成功、zero-finding/degraded、expected port failure、store failure、unexpected exception 和 invalid record semantics。
