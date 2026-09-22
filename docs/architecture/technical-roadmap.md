# ArkUI Repository-aware Code Review Service 技术路线

## 1. 当前产品方向

当前使用的产品版本是已完成的 **Fast-MVP — GitCode ArkUI Automated Code Review**：

```text
GitCode PR
  → PR metadata / base SHA / head SHA / diff
  → author whitelist
  → full review identity dedup
  → prepare target ArkUI revision
  → Codex / Code Agent + ArkUI Code Review Skill
  → Docs KB + Live Source
  → structured findings
  → GitCode PR summary comment
  → persist completed review identity
```

P1/P2 是保留的历史实现，不参与当前产品运行链路。

Fast-MVP 优先复用现成 GitCode API/MCP、Codex CLI，以及经 smoke 验证后确有价值的 OpenCodeReview 能力。当前不自行建设完整 MCP Server，也不建设 generic Agent Runtime。自动 polling、author filter、完整 review identity dedup、knowledge refresh 和状态持久化属于轻量 Fast-MVP service/CLI，不属于 Skill 或外部 Agent。

本文件是当前长期产品方向和架构边界的最高层 source of truth。阶段与 Definition of Done 见 [Phase Map](../exec-plans/phase-map.md)，已完成的具体执行见 [Fast-MVP execution plan](../exec-plans/completed/Fast-MVP-code-review.md)。既有专题架构与 [ADR-0005](../decisions/ADR-0005-code-review-service-pivot.md) 保留旧 R0–R6 路线的设计价值和历史背景，但不再决定当前执行顺序。

## 2. Fast-MVP 架构

```text
arkui-review CLI / lightweight service
├── GitCode minimal adapter (existing API/MCP preferred)
├── manual review command
├── polling loop + author whitelist
├── full identity dedup + simple state
├── knowledge update/status
├── Codex non-interactive runner
└── result formatter/publisher
             │
             ▼
skills/arkui-code-review/
             │
             ▼
Repository evidence
├── Docs KB / kb_search          required
└── Live Source / Git / rg       required and authoritative
             │
             ▼
Structured review result → GitCode summary comment
```

MVP 可以复用 R0 已实现的 platform-neutral domain model、ports、configuration/error/observability 基础，但不得为了适配旧抽象而阻塞闭环。对既有 contract 的行为修改仍须遵循 spec 与测试规则。

## 3. 核心边界

### 3.1 GitCode 与触发

- GitCode 私有 schema、鉴权和错误应停留在最小 adapter 边界；优先复用已有 GitCode API/MCP implementation。
- 第一版只需要读取 open PR、metadata、author、base/head SHA、changed files/diff，并发布一个 summary comment。
- 自动流程固定为 `poll → author filter → full identity dedup → knowledge prepare → review → publish → persist`。
- polling interval、repository 和 author whitelist 必须可配置；Skill 不维持后台 polling。
- Fast-MVP 自动 dedup 使用 `repository + pr_id + base_sha + head_sha + review_policy_version`；base 变化即使 head 不变也要重新 review。R0 四字段 `ReviewIdentity` 保留为历史 contract。
- 状态可使用简单 JSON 或 SQLite；不引入 Redis、Celery、Kafka 或 distributed queue。

### 3.2 Codex runner 与 Skill

- Codex CLI 以非交互方式运行，输入绑定明确的 PR 和 repository revision。
- Agent 成功返回 zero findings 与 Agent failure 必须是不同结果。
- `skills/arkui-code-review/` 指导 Agent 读取 diff、补充函数上下文、检索知识、判断证据并输出结构化结果。
- Skill 可以指导 Codex 或其他 Code Agent 使用可用工具，但不拥有 scheduler、dedup、credentials、knowledge persistence 或 review state。
- Fast-MVP 不自行开发完整 MCP Server；可以调用第三方 GitCode MCP 或其他现成接口。

### 3.3 Knowledge strategy

Fast-MVP 的知识路径是 `Docs KB + Live Source`：

- Docs KB / `kb_search` 提供 ArkUI 架构、组件、领域规则和术语背景。
- Live Source 使用 Git、filesystem 和 `rg` 读取目标 repository 当前 revision；它是源码事实的最终 source of truth。
Docs KB 不可用时，只有 Live Source 与 review policy 的证据足够才能继续 degraded review。Live Source 无法准备到目标 revision 时不能伪装成功。P1/P2 不参与当前知识准备、review 或 refresh。

Knowledge update 支持手动 `arkui-review knowledge update`、`arkui-review knowledge status` 和每日自动 refresh。每日最低刷新 ArkUI repository 与 Docs KB revision，并使 Live Source 指向目标 revision；当前 runtime 不配置或刷新 P1/P2。

### 3.4 Review result

首阶段 review category：

- Stability；
- Memory / Resource / Lifetime；
- Functional Correctness。

结构化 finding 至少包含 file、可确定时的 line/range、category、severity、evidence、explanation 和 recommendation。Finding 必须有与目标 revision 对齐的源码证据；知识背景不能覆盖相冲突的 Live Source。证据不足时不产生 finding，zero findings 是合法成功结果。第一版只发布一个结构清晰的 PR summary comment，不要求精确 inline comment。

## 4. 历史基础保持不变

### P0/P1/P2

P0、P1、P2 是已完成历史基础。completed plans、specs、tests、frozen fixtures 和 evaluation baseline 均保留；P1/P2 不进入当前 Fast-MVP 产品，也不删除或重写 frozen semantics。

### P3-A～E

已完成 P3-A～E contract 继续描述当前代码已实现的 Task/Change input、snapshot read、candidate retrieval、change mapping、graph expansion 和 context materialization 行为。Fast-MVP 可选择性复用，但不追溯改写为新的 MVP contract。未完成的 P3 后续与旧 P4/P5 路线继续保持 `Superseded`。

### R0–R6 路线

原完整自研 R0–R6 Service/MCP 路线整体已被 Fast-MVP 路线取代，不再作为当前执行主线：

- R0 已完成的 foundation 实现与 specs 是历史事实，可被 MVP 复用，不改标为未完成或 Superseded phase。
- R1–R6 未完成计划均为 `Superseded by Fast-MVP route`，不得继续按原顺序实施或标记 Completed。
- 原路线的 provider、evidence、revision、dedup 等设计可作为参考，但完整 Repository Knowledge Service、Review Engine、MCP Server 和生产级 job platform 均不是 MVP 前置条件。

## 5. 当前开发路线

```text
M0 Foundation & External Tool Smoke
 → M1 GitCode Minimal Integration
 → M2 Code Agent Review Runner (Codex first backend)
 → M3 ArkUI Knowledge & Review Skill
 → M4 GitCode Review Publishing
 → M5 Auto Polling & Knowledge Refresh
 → M6 Demo Validation & Hardening
```

Fast-MVP 的阶段边界以 [Phase Map](../exec-plans/phase-map.md) 为准。已完成计划是 [Fast-MVP-code-review.md](../exec-plans/completed/Fast-MVP-code-review.md)；M0–M6 已完成。当前使用这一 MVP 版本，CLI runtime 使用 Docs KB 与 Live Source；没有后续开发计划。

## 6. 当前使用边界

已验收的 Fast-MVP 是当前使用版本。日常使用沿用现有 CLI/service、GitCode adapter、Codex runner、ArkUI Review Skill、Docs KB 与 Live Source。P1/P2、完整 Repository Knowledge Service、内部 MCP Server、durable job system 和 generic Agent Runtime 均不属于当前产品范围。历史 P1/P2/P3/R0 实现事实与验收记录继续保留。
