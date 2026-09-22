# R1 — GitCode Integration & Review State

- **Phase Status:** Superseded
- **Planning Status:** Superseded
- **Superseded by:** [Fast-MVP — GitCode ArkUI Automated Code Review](../completed/Fast-MVP-code-review.md)
- **Superseded reason:** Superseded by Fast-MVP GitCode automated review route
- **Current implementation milestone:** None; all R1 milestones remained Not Started
- **Depends on:** completed R0 Review Service Foundation
- **Architecture:** [Technical Roadmap](../../architecture/technical-roadmap.md), [Code Review Architecture](../../architecture/code-review-architecture.md)
- **Historical route status:** [Phase Map historical phases and superseded routes](../phase-map.md#3-historical-phases-and-superseded-routes)
- **Foundation contracts:** [R0 completed plan](../completed/R0-review-service-foundation.md), [Review Service specs](../../specs/review-service/README.md)

## Goal

> **Superseded by Fast-MVP GitCode automated review route.** 本计划未开始实现，因此没有标记 Completed。以下内容保留原 R1 设计、范围与所有 milestone 的 `Not Started` 历史状态，不得从本文件继续开发。

可靠地把 GitCode Pull Request 的 metadata 与 exact revision change 转换为 R0 已冻结的 `ReviewIdentity` / `ReviewRequest`，在 review user filter 后以 durable atomic claim 管理重复提交、失败、重试和重启恢复，并提供不依赖 Review Engine 的手动 `review_pr` ingestion path。

本文原只规划 R1，且没有任何 R1 milestone 开始实现。路线切换后不得再从本计划选择 milestone；当前工作必须遵循 Fast-MVP active plan。

## In scope

- `GitCodeProvider` 真实 read adapter；
- PR locator、metadata、author、base/head SHA、diff、changed files/hunks 的平台无关 normalization；
- GitCode public configuration、authentication secret、pagination、bounded read retry 与 error mapping；
- review users 的 set/get、持久化和 author filter；
- 基于 R0 `ReviewIdentity` 的 durable dedup 与 atomic claim；
- job/result durable state、failed/expired claim retry 和 restart recovery；
- manual `review_pr` application ingestion；
- R1 specs、unit/contract/integration/fault tests 与 phase traceability。

## Out of scope

- DocsKb/LiveSource/P1/P2 provider、KnowledgeGateway implementation 或 knowledge refresh；
- ReviewContextPack、LLM/review reasoning、finding generation 或 category policy；
- MCP transport/tools；
- PR Poller、Scheduler、webhook 或 auto review loop；
- GitCode comment publishing/write API；
- generic Agent Runtime、source edit、build/test/repair workflow；
- 修改 P1/P2/P3 frozen semantics、fixtures 或 baseline。

## R0 contract reuse and extension rules

R1 必须复用而不是复制 R0 contract：

1. `ReviewIdentity(repository, pr_id, head_sha, review_policy_version)` 仍是唯一 review/dedup identity；不新增 GitCode-specific identity。
2. `ReviewRequest` 仍是 normalization 的 canonical review input；GitCode DTO、pagination response 和 transport error 只能存在于 adapter 内部。
3. R1 可以增加只表达 R0 尚未承载信息的窄 companion types，例如 PR locator、author/metadata、claim/attempt 和 ingestion outcome；这些类型不得复制 diff、finding、result 或 identity fields 成为第二套 review model。
4. R0 `GitCodeProvider` 在 R1-A 兼容扩展为 two-step read boundary：先用 repository + PR id 读取 metadata/head，再以完整 R0 identity exact-load `ReviewRequest`。既有 exact-identity behavior 不删除。
5. R0 `ReviewJobState` / `ReviewJobRecord` 继续表示 review lifecycle。Claim/attempt metadata 只解决 durable concurrency/retry/restart，不另建平行 findings/result lifecycle。
6. R0 `ResultStore` 以兼容方式扩展 durable claim/query capability；application 仍只依赖 ports，不依赖 SQLite 或 GitCode transport。
7. Public config 扩展 R0 `ReviewServiceConfig` boundary；credential 只通过 `ReviewConfigurationSource.get_secret` / `SecretValue` 到达 adapter 最晚使用点。
8. GitCode/config/store/application failures 映射到 R0 error taxonomy；公开状态、`str`/`repr`、diagnostic 和 persisted result 不包含 private reason 或 secret。
9. R1 diagnostics 使用 R0 `ReviewCorrelation`、`ReviewDiagnostic` 和 `DiagnosticSink`；correlation 不进入或改变 `ReviewIdentity`。

## Milestone sequence

| Milestone | Scope | Depends on | Status |
| --- | --- | --- | --- |
| R1-A | PR read/normalization contracts | R0 | Not Started |
| R1-B | GitCode read adapter and transport safety | R1-A | Not Started |
| R1-C | Review users and author filter | R1-A | Not Started |
| R1-D | Durable state, atomic claim and retry/restart | R1-A, R1-C | Not Started |
| R1-E | Manual `review_pr` ingestion orchestration | R1-B–D | Not Started |
| R1-F | Integration, traceability and phase acceptance | R1-A–E | Not Started |

一次 Codex coding task 默认只执行一个 milestone。R1-B、R1-C 和 R1-D 在 R1-A contract 冻结后可以独立准备，但不得跨 milestone 提前实现 R1-E 或任何 R2+ behavior。

## R1-A — PR Read and Normalization Contracts

- **Status:** Not Started
- **Goal:** 补齐 manual PR lookup 到 exact R0 identity/request 的平台无关 contract，并冻结 GitCode schema 隔离与 revision consistency。
- **Deliverables:** 最小 PR locator/metadata/author companion types；既有 `GitCodeProvider` 的 metadata-read 与 exact-revision read 扩展；GitCode adapter-private DTO boundary；PR/diff/files/hunks → R0 `ReviewRequest` normalization rules；representative fixtures、contract tests 和 spec。
- **Acceptance Criteria:** manual input 在未知 head 时可先读取 metadata，再用返回的 exact head 构造 R0 `ReviewIdentity`；normalization 确定地产生 R0 `ReviewRequest` / `ChangeRef`，保留 base/head、完整 diff、changed files 和每个可定位 hunk range；metadata 与 diff 的 head 不一致时显式失败，不能把新 revision 内容写到旧 identity；GitCode-only fields/errors 不越过 adapter boundary；没有第二套 ReviewIdentity、ReviewRequest、ReviewResult 或 Finding。
- **Non-goals:** HTTP/auth、durable store、user filter、manual orchestration、knowledge/review execution。

## R1-B — GitCode Read Adapter and Transport Safety

- **Status:** Not Started
- **Goal:** 实现受配置约束、可测试且不泄漏凭据的 GitCode read adapter。
- **Deliverables:** GitCode public config extension；通过 R0 `SecretValue` 获取 authentication credential；bounded HTTP transport；metadata/diff/changed-files read calls；pagination termination/limits；transient read retry policy；GitCode HTTP/schema/error → `GitCodeProviderError` mapping；safe diagnostics；unit/contract integration tests and spec。
- **Acceptance Criteria:** adapter 覆盖 PR metadata、author、base/head SHA、diff、changed files/hunks；所有分页有 page/item 上限并拒绝循环或截断伪完整；retry 仅用于明确 transient、幂等 read failure，attempt/time/backoff 都有上限；auth/permission/not-found/rate-limit/schema/transport failure 有稳定分类且不会生成 success；credential/raw authorization 不进入 repr、exception public message、diagnostic、persisted state 或 test artifact；测试不依赖真实 GitCode credential。
- **Non-goals:** GitCode write/comment、polling/webhook、通用 HTTP SDK、scheduler retry loop。

## R1-C — Review Users and Author Filter

- **Status:** Not Started
- **Goal:** 冻结 review-user configuration contract，并在昂贵 diff/review 工作前执行确定性 author filter。
- **Deliverables:** review-user store port；set/get application APIs；trimmed、unique、stable-order username contract；author eligibility decision/result；filter diagnostics；unit/contract tests and spec。
- **Acceptance Criteria:** set/get 与 filter contract 确定；username matching semantics、empty-set behavior 和 invalid input 在 spec 中固定；filter 使用 GitCode normalized author，不读取 GitCode private schema；不符合用户集合的 PR 在获取完整 diff、claim 或调用下游 review 前停止；配置与 diagnostics 不包含 credential；manual path 不提供未规划的 force/bypass。
- **Non-goals:** MCP `set_review_users` / `get_review_users` transport、scheduler candidate polling、organization/team policy。

## R1-D — Durable State, Atomic Claim and Retry/Restart

- **Status:** Not Started
- **Goal:** 以 R0 identity/lifecycle 为核心建立 durable、可查询、并发安全的 review state。
- **Deliverables:** R0 `ResultStore` 的兼容 claim/query extension；初始 SQLite-backed durable adapter 与 schema version/migration boundary；identity unique constraint；claim lease/owner/attempt metadata；request/job/result persistence；failed/expired retry 与 restart recovery semantics；R1-C review-user store 的 durable implementation；concurrency/crash/fault tests and spec。
- **Acceptance Criteria:** 同一 R0 identity 在 concurrent submission、重复调用和 restart 后最多一个有效 claim；succeeded identity 是 dedup terminal，不能被普通 retry 重跑；failed 或 expired claim 可在同一 identity 下创建单调 attempt，而不是伪造新 identity；新 head 或 policy version 是独立 identity；running/claim 状态不会在重启后被误报 succeeded；request/job/result/state 可查询；review users 在 restart 后可恢复；transaction/storage failure 不写入 false success；数据库不保存 credential、private error reason 或 Repository Knowledge 副本。
- **Non-goals:** multi-node distributed consensus、scheduler-owned automatic retry/backoff、result retention/archival policy、Repository Knowledge storage。

## R1-E — Manual `review_pr` Ingestion Orchestration

- **Status:** Not Started
- **Goal:** 将 R1-A～D 组合成不依赖 Knowledge/Review Engine 的手动 PR ingestion application path。
- **Deliverables:** manual `review_pr` application command/service；typed accepted/filtered/duplicate/failed outcomes；metadata → user filter → R0 identity → atomic claim → exact-revision normalization → pending durable job flow；status/result query application APIs needed by R1；retry/restart contract tests and spec。
- **Acceptance Criteria:** 同一输入可确定返回 accepted、filtered、duplicate/in-flight、existing-success 或 failed outcome；author filter 先于完整 diff 和 claim；claim 后读取到不同 head 时终止旧 claim并以显式 revision-change outcome 返回，不混合 revision；accepted request 只持久化为 R0 pending job，不调用 KnowledgeGateway/ReviewEngine、不制造 findings 或 success；provider/normalization/storage failure 不产生 false successful record；failed/expired retry 遵循 R1-D semantics；application 不导入 concrete GitCode/SQLite adapter。
- **Non-goals:** `review_diff`、MCP handler、background queue/worker、KnowledgeGateway、Review Engine 或 auto review。

## R1-F — Integration, Traceability and Phase Acceptance

- **Status:** Not Started
- **Goal:** 用跨 adapter/application/storage 的证据完成 R1 Definition of Done，而不把后续能力计入完成度。
- **Deliverables:** GitCode integration/normalization spec；review-user/filter spec；durable review-state/dedup spec；manual ingestion spec；R1 traceability matrix；security/redaction、pagination/retry、concurrency/restart/failure integration tests；docs index/status updates。
- **Acceptance Criteria:** Phase Map R1 DoD 1–7 每项都有 spec/implementation/test evidence；representative GitCode payload、pagination、head drift、filtered author、duplicate identity、new head/policy、concurrent claim、failed retry、restart recovery、provider/store failure 和 credential redaction 均有确定测试；required validation 通过后才将 R1-F 与 R1 Phase 标记 Completed并归档计划；验收材料不宣称 R2+ behavior。
- **Non-goals:** live production rollout、正式 quality benchmark、R2 knowledge、R3 reasoning、R4 MCP 或 R5 scheduler。

## Cross-cutting lifecycle decisions to freeze during implementation

### Manual lookup and revision binding

Manual `review_pr` 的初始输入不是 `ReviewIdentity`，因为调用前未知 `head_sha`。R1-A 只增加最小 PR locator/metadata companion contract；metadata 返回 exact head 后立即构造 R0 identity，后续 diff normalization、claim 和 persistence 都必须绑定该 identity。任何 head drift 都显式失败或重新开始新 identity，不能原地改写 identity。

### Filter ordering

固定顺序为：

```text
PR locator
  → lightweight metadata/author
  → review user filter
  → ReviewIdentity
  → atomic claim/dedup
  → exact-revision diff/files/hunks
  → normalized ReviewRequest
  → persist pending job
```

R1 不轮询 PR，也不调用 KnowledgeGateway/ReviewEngine。Filter、dedup 和 exact-revision load 必须能由 fakes 独立验证。

### Retry boundaries

- GitCode transport retry：R1-B 内部的 bounded transient read retry，不改变 review identity。
- Review attempt retry：R1-D 的显式 failed/expired claim retry，复用同一 identity 并增加 attempt。
- Succeeded review 不由普通 retry 重跑；force semantics 若未来需要，必须独立规划。
- R1 不实现 scheduler/background automatic retry loop。

### Durable storage boundary

初始本地部署使用 SQLite adapter，但 schema、transaction 和 SQL 不泄漏到 domain/application ports。存储目录由显式配置提供，不使用 target repository 目录，不复用或修改 P1/P2 database。并发 claim 必须由数据库原子约束/transaction 保证，不能只靠进程内锁或先查后写。

## Validation plan

实现各 milestone 时：

- 行为变更新增或更新对应 `test_*.py`；
- Codex 不主动执行测试，由 trusted Stop Hook 按 AGENTS.md 运行工作树相关测试；
- HTTP 使用 deterministic fake transport/server，不要求外部 GitCode 可用或真实 credential；
- concurrency/restart/fault tests 使用临时 durable store，不持久化 runtime database 到仓库；
- strict full、真实 GitCode smoke、ArkUI baseline 或昂贵验证只由用户显式触发；
- 文档相对链接与 schema references 做静态检查；
- 完成前运行 `git diff --check`。

本次仅创建计划和同步索引，不运行产品测试，也不把任何 R1 milestone 改为 `In Progress` 或 `Completed`。

## Phase acceptance checklist

- [ ] R1-A Completed
- [ ] R1-B Completed
- [ ] R1-C Completed
- [ ] R1-D Completed
- [ ] R1-E Completed
- [ ] R1-F Completed
- [ ] R1 specs describe implemented behavior only
- [ ] Required targeted tests passed through the trusted validation path
- [ ] Phase Map R1 DoD fully traceable
- [ ] No R2+ behavior claimed as implemented

## Risks and controls

- **Head drift:** metadata/head 与 diff head 分两次读取；exact-revision check 不通过时失败或以新 identity 重启，绝不混合。
- **Platform leakage:** GitCode JSON、pagination token、HTTP status/header 和 transport exceptions 只存在于 adapter/tests fixtures。
- **Duplicate race:** durable unique constraint + atomic transaction 是 correctness boundary，不能用 in-memory pre-check 代替。
- **False success:** ingestion 只产生 filtered/duplicate/failed 或 pending；R1 没有 Review Engine，不产生 findings/succeeded result。
- **Credential leakage:** credential 使用 R0 `SecretValue`，测试覆盖 repr/log/diagnostic/error/persistence redaction。
- **Retry amplification:** transport retry 和 review attempt retry 分层且都有显式边界；R1 不启动后台重试。
- **Scope creep:** Scheduler/MCP/Knowledge/LLM adapter 均保留在 R2–R5，不因 manual path 提前实现。
