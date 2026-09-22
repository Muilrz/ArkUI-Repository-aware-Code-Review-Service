# Fast-MVP — GitCode ArkUI Automated Code Review

- **Route Status:** Active
- **Current milestone:** M5 — Auto Polling & Knowledge Refresh
- **Current milestone status:** In Progress
- **Supersedes:** incomplete R1–R6 complete Service/MCP route
- **Reuses:** completed P0/P1/P2, P3-A～E contracts, and R0 Review Service Foundation where useful
- **Architecture:** [Technical Roadmap](../../architecture/technical-roadmap.md)
- **Phase boundary:** [Phase Map](../phase-map.md)

## Context

交付目标已从按 R0→R6 顺序建设完整自研 Code Review Service、Repository Knowledge Service 和 MCP Server，切换为在极短时间内交付可运行、可演示的 GitCode ArkUI 自动代码检视 MVP。R0 已完成的基础与 P1/P2/P3 历史能力保留；未开始的 R1–R6 不再是当前执行计划。

本计划只定义 Fast-MVP 实施。创建和激活本计划不表示任何 M0–M6 产品能力已完成；开始 coding 时只把明确选择的 milestone 改为 `In Progress`。

## Goal

交付手动与自动均可触发的最小闭环：

```text
GitCode PR
  → metadata / base SHA / head SHA / diff
  → author whitelist
  → full review identity dedup
  → prepare ArkUI repository revision
  → non-interactive Codex / Code Agent
  → ArkUI Code Review Skill
  → Docs KB + Live Source + optional P1/P2
  → structured findings or valid zero findings
  → GitCode PR summary comment
  → persist completed review identity
```

## Non-goals

- generic Agent Runtime、planning platform、长期 memory 或任意工具编排；
- 自行开发新的完整 MCP Server；
- 完整 Review Engine/platform、distributed scheduler 或 production job system；
- Redis、Celery、Kafka、distributed queue 或 multi-node coordination；
- GitCode issue/milestone/release/merge automation、复杂 reviewer management 或 webhook system；
- 第一版精确 inline review comment；
- 修改 P1/P2 产品代码、frozen semantics、fixtures、baseline 或 P3-A～E 历史 contract；
- source edit、build/test/repair 或 UT Development 产品线；
- 在 MVP 价值验证前扩展为完整长期平台。

## Architecture

`arkui-review` 是轻量 CLI/package 和可常驻 loop：

- GitCode minimal adapter 读取 PR context，并发布 summary comment；
- manual command 处理单个 PR；poller 按 interval 扫描 open PR；
- author whitelist 在昂贵 review 前执行；
- state store 以 `repository + pr_id + base_sha + head_sha + review_policy_version` 去重；
- repository preparer 将 Live Source 对齐到目标 revision；
- Codex runner 非交互调用 Code Agent，并校验 structured result；
- ArkUI Review Skill 规定知识获取、证据和 review category；
- formatter 将 findings 或 zero-findings success 转换为一个 PR summary comment。

优先复用 R0 已实现的 domain/config/error/observability boundary，但只在不增加闭环复杂度且不改变已实现 contract 时复用。

## External dependencies

- **GitCode API or GitCode MCP:** 优先复用已有实现完成 PR read/comment write；M0 用真实 PR smoke 决定具体路径。
- **Codex CLI:** 必须支持非交互执行、可捕获 exit/result，并能约束结构化输出。
- **OpenCodeReview:** 可选；只在 smoke 后证明能显著缩短交付时复用，不成为 MVP 必需依赖。
- **ArkUI target repository:** 由显式配置提供，默认只读，不 vendor 到本仓库。
- **Docs KB / `kb_search`:** MVP 必需的领域知识来源。
- **P1/P2:** 本仓库已有能力，可选接入，不是 availability gate。

Credentials 不进入仓库、日志、structured findings 或持久化 review result。外部工具失败必须映射为可诊断 failure，不能被当作 zero findings。

## Knowledge strategy

每次 review 绑定 `base_sha`、`head_sha` 和目标 ArkUI repository revision。知识获取顺序是：

1. 读取 changed diff 与修改函数上下文；
2. 用 Docs KB / `kb_search` 获取架构和领域规则；
3. 用 Git、filesystem、`rg` 核实目标 revision 的真实源码；
4. 按需查询 P1 symbols、definition、references、callers、callees、tests；
5. 按需查询 P2 ArkUI role、framework relations 和 bounded traces；
6. 对每条 finding 保留可复核 evidence。

Live Source 是当前源码事实的最终 source of truth。P1/P2 只有在 revision 对齐或兼容语义明确时才能支持 current-fact claim；否则排除该 claim，并记录 stale/unavailable/degraded。Docs KB + Live Source 必须能独立完成 review。

## Review categories and result contract

第一阶段只关注：

- Stability；
- Memory / Resource / Lifetime；
- Functional Correctness。

Structured result 至少表达 status、repository/PR/base/head identity、provider/degradation 状态和 findings。每条 finding 至少包含 file、可确定时的 line/range、category、severity、evidence、explanation 和 recommendation。只有足够且与目标 revision 对齐的源码证据才能产生 finding。

成功结果允许 `findings: []`。Agent invocation failure、timeout、invalid schema、revision preparation failure、GitCode read failure 和 publish failure 均不得伪装成 zero findings 或 completed review。

## Milestones

### M0 — Fast-MVP Foundation & External Tool Smoke

- **Status:** Completed
- **Scope:** 验证非交互 Codex；以真实 PR 验证 GitCode API/MCP read；可选 OpenCodeReview smoke；建立最小 `arkui-review` CLI/package 与 config。
- **Acceptance:** smoke 结果足以选择 GitCode/Codex 集成方式；CLI 可启动并读取最小配置；不实现 review engine、MCP Server、scheduler framework 或 P1/P2 refresh。

### M1 — GitCode Minimal Integration

- **Status:** Completed
- **Scope:** list/open PR、metadata、author、base/head SHA、changed files/diff，以及发布 summary comment 的最小 boundary。
- **Acceptance:** `arkui-review review --pr <PR_ID>` 能获取并打印真实、revision-bound PR context；无 MVP 外 GitCode 功能。

### M2 — Code Agent Review Runner

- **Status:** Completed
- **Scope:** PR context → platform-neutral Code Agent boundary → selected backend → validated JSON result；Codex is the first validated backend。
- **Acceptance:** 上层不依赖 Codex-specific command/output；structured findings、valid zero findings、Agent failure/invalid output 明确区分；第一版无需 inline comment。

### M3 — ArkUI Knowledge & Review Skill

- **Status:** Completed
- **Scope:** 建立 `skills/arkui-code-review/`，指导 diff/context、Docs KB、Live Source、optional P1/P2 和三类 review。
- **Acceptance:** Docs KB + Live Source 可独立完成 degraded review；stale P1/P2 不被当作当前确定事实；无证据不产生 finding。

### M4 — GitCode Review Publishing

- **Status:** Completed
- **Scope:** structured result → formatter → one GitCode PR summary comment。
- **Acceptance:** finding 包含所需字段；zero-findings success 有明确摘要；publish failure 不写成功状态。
- **Real smoke:** `muil793608902/arkui-review-test#1` 成功发布 summary comment `60cc6468c819a0903477d54f1ebe03bb2f2007b0`（用户确认）。

### M5 — Auto Polling & Knowledge Refresh

- **Status:** In Progress
- **Scope:** configurable polling/repository/author whitelist；full review identity dedup；JSON/SQLite state；manual/daily knowledge refresh。
- **Acceptance:** `list → filter → dedup → prepare → review → publish → persist` 可运行；`knowledge update/status` 可用；每日检查 repository、Docs KB revision 和 Live Source；P1/P2 不进入 M5 runtime refresh，unavailable/stale 不阻塞 review。
- **Current limit:** fetch 只更新 Git metadata；不自动 checkout 或改写外部 ArkUI worktree。目标 HEAD 未对齐时 review 明确失败，真实 revision preparation/daily refresh 验收仍待验证。

### M6 — Demo Validation / Hardening

- **Status:** Not Started
- **Scope:** 只验证并修复真实 MVP 闭环。
- **Acceptance:** manual/poll trigger、whitelist、interval、same-head suppression、new-head review、manual knowledge update、degraded review 和 GitCode comment 均有真实验证证据。

## Acceptance Criteria

Fast-MVP 完成必须同时满足：

1. 能手动 review 单个真实 GitCode PR。
2. 可配置 polling interval、repository 与 author whitelist。
3. 同一完整 review identity 不重复 review；base、head 或 policy version 变化可重新 review。
4. 非交互 Codex 产生通过 schema 校验的 structured result。
5. 三类 review 使用与目标 revision 对齐的源码证据；zero findings 合法且与 failure 区分。
6. Review 结果可发布为 GitCode PR summary comment，成功发布后才持久化 reviewed identity。
7. `arkui-review knowledge update/status` 与每日 refresh 可用。
8. P1/P2 unavailable、stale 或 refresh failure 时，Docs KB + Live Source degraded path 仍可 review 并报告 degradation。
9. P1/P2/P3/R0 已实现 contract、fixtures 和 baseline 未被追溯改写。

## Degraded behavior

- P1 unavailable/stale/error：停止使用其 current-fact claims，报告状态，继续 Docs KB + Live Source。
- P2 unavailable/stale/error：停止使用其 semantic relation claims，报告状态，继续 Docs KB + Live Source，可保留已验证的 P1。
- Docs KB 暂不可用：报告 degraded；只有 Live Source 和 review policy 足以支持具体 finding 时才继续，不猜测领域事实。
- Live Source 无法对齐目标 head revision：review 失败，不发布成功评论，不持久化 reviewed head。
- Codex/Agent、schema validation 或 GitCode publish 失败：保留可重试诊断，不记录成功 dedup。
- 无足够证据或没有问题：成功返回 zero findings，不制造 finding。

## Validation

每个 coding milestone 的行为变更必须新增或更新对应测试；Codex 不主动运行产品测试，由 trusted Stop Hook 按 `AGENTS.md` 执行工作树相关 `test_*.py`。真实 GitCode/Codex/ArkUI smoke 与 demo validation 只在相应 milestone 明确要求时运行；strict full、ArkUI baseline 和昂贵验证由用户显式触发。

M0/M1 明确允许执行 Codex CLI capability smoke、真实 GitCode public-read smoke 与真实 `arkui-review review` 命令。产品测试仍由 trusted Stop Hook 只选择工作树新增或修改的 `test_*.py`；不主动运行 full tests 或 ArkUI baseline。

## Demo Definition of Done

明天前 MVP 的核心 DoD：

```text
真实 GitCode PR
  → 获取 PR
  → author filter
  → Codex review
  → ArkUI knowledge retrieval
  → structured findings or valid zero findings
  → GitCode comment
  → full review identity dedup
```

演示必须至少显示一个真实 PR、所用 head SHA、knowledge/degradation 状态、结构化结果、已发布 summary comment，以及重复触发未产生第二次 review；若 PR 更新为新 head，能够重新 review。

## Explicitly deferred work

- 完整 Repository Knowledge Service/KnowledgeGateway platform；
- 自研完整 Review Engine 和通用 policy orchestration；
- 自研 MCP Server 与完整 public tool surface；
- production scheduler/job manager、distributed state、HA、webhook；
- inline review comments、复杂 reviewer workflow 和 merge automation；
- 大规模 benchmark、完整 ablation、production SLO/security/performance hardening；
- P1/P2 incremental refresh 重构或 frozen semantics 变更；
- generic Agent Runtime、coding/repair/UT workflow。

这些能力只有在 MVP 验证价值后，由新的明确计划决定是否恢复或重新抽象。
