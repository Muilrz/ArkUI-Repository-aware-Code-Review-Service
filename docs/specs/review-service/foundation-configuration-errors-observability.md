# Foundation Configuration, Errors and Observability

## Scope

本文定义 R0-D 已实现的安全 configuration/loading boundary、统一 failure taxonomy、review/job correlation 和 structured diagnostic contract。它不实现配置文件或环境变量 loader、GitCode credentials、production logging/telemetry backend、retry/backoff、scheduler 或任何 R1+ adapter behavior。

## Configuration boundary

`ReviewServiceConfig` 只承载公共、可安全显示的 foundation 配置；R0-D 唯一字段是非空 `review_policy_version`。GitCode endpoint、credential、timeout 和其他平台配置属于 R1。

`ReviewConfigurationSource` 分开暴露：

```text
load_service_config() -> ReviewServiceConfig
get_secret(name) -> SecretValue | None
```

公共配置不含 secret dictionary 或 credential field。R0-D 只定义 structural port，不提供 filesystem、environment、vault 或 GitCode loader。

`SecretValue`：

- 保留 adapter 显式调用所需的原值；
- `str`、`repr` 和普通 format 始终输出 `<redacted>`；
- 只有显式 `reveal()` 才返回原值；
- `reveal()` 的结果不得进入 exception、log、diagnostic、job/result 或其他公开模型。

## Error taxonomy

R0-D 不替换 R0-C 的 `ReviewJobFailure`。它为 domain、application、port 和 unexpected failure 提供统一公开分类：

| Category | Existing/new failure source |
| --- | --- |
| `validation` | domain model 的 `ValueError` |
| `configuration` | `ReviewConfigurationError` |
| `application` | `ReviewApplicationError` 或基础 port failure |
| `gitcode_provider` | `GitCodeProviderError` |
| `knowledge_gateway` | `KnowledgeGatewayError`；R0-C knowledge-stage job failure |
| `review_engine` | `ReviewEngineError`；R0-C engine-stage job failure |
| `result_store` | `ResultStoreError` |
| `internal` | 未声明 exception |

`classify_review_failure` 返回 `ReviewErrorInfo(category, code, message)`。`code` 和 `message` 是稳定公开信息；不会复制原 exception reason 或 R0-C job failure reason。原有 port error 只在显式 `.reason` 保留内部 detail；`str`、`repr` 和 Job Manager 持久化的 failure reason 都使用固定公开 message。R0-C knowledge/engine state transition 和 `ReviewJobFailure` 结构不变。

R0-D 不定义 retryable flag、HTTP/MCP mapping、status code 或 provider-specific detail；这些属于使用该 taxonomy 的后续阶段。

## Correlation contract

`ReviewCorrelation` 只包含：

```text
correlation_id
job_id
```

两个字段都是非空 operational identifier。它不包含、派生或替代 `ReviewIdentity`，不会改变 `repository + pr_id + head_sha + review_policy_version` equality/dedup boundary。ID generation、persistence 和跨进程 propagation 属于后续实现。

## Structured diagnostics

`ReviewDiagnostic` 包含 correlation、level、稳定 code、公开 message 和有序 attributes。Level 仅为 `info`、`warning`、`error`。Attributes：

- name 唯一且非空；
- value 只允许 string/number/boolean/null；
- non-finite float 被拒绝；
- `SecretValue` 和名称包含 token/password/secret/credential/authorization/cookie/private-key 标记的字段统一保存为 `<redacted>`；
- canonical JSON 不包含 private failure reason。

`ReviewDiagnostic.from_failure` 使用统一 taxonomy 构建 error diagnostic，只记录 failure type，并在输入是 R0-C `ReviewJobFailure` 时记录 failure stage；它不复制原始 reason。`DiagnosticSink` 是 structural port；R0-D 不提供 console/file/OTel/backend implementation，也不改变 Review Job Manager 的执行路径。

## Secret exclusion

R0-D 的公开 config、correlation、diagnostic 和 error-info contract 都不提供 secret 输出字段。R0-B/R0-C 的 `ReviewResultSummary`、`ReviewFinding` 与 `ReviewJobRecord` 未增加 config、credential 或 diagnostic payload。未来 adapter 必须持有 `SecretValue` 到最晚使用点，并禁止把 `reveal()` 结果拼入异常、日志或结果。

## Non-goals

- GitCode authentication 或 credential name/schema；
- config loader implementation 或 environment variable naming；
- telemetry backend、metrics、span、timestamp 或 log retention；
- correlation-based dedup 或 identity derivation；
- retry、timeout、backoff、scheduler、knowledge provider、LLM 或 MCP。
