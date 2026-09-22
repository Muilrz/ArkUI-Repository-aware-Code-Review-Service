# Fast-MVP — GitCode ArkUI Automated Code Review

- **Route Status:** Completed
- **Final milestone:** M6 — Demo Validation / Hardening (Completed)
- **Supersedes:** incomplete R1–R6 complete Service/MCP route
- **Reuses:** completed P0 and R0 foundation where useful; preserves P1/P2/P3-A～E historical contracts for future optional use
- **Architecture:** [Technical Roadmap](../../architecture/technical-roadmap.md)
- **Phase boundary:** [Phase Map](../phase-map.md)

## Context

交付目标已从按 R0→R6 顺序建设完整自研 Code Review Service、Repository Knowledge Service 和 MCP Server，切换为在极短时间内交付可运行、可演示的 GitCode ArkUI 自动代码检视 MVP。R0 已完成的基础与 P1/P2/P3 历史能力保留；未开始的 R1–R6 不再是当前执行计划。

本计划记录 Fast-MVP M0–M6 的实施范围与验收状态。Milestone 只有在 Acceptance Criteria 与必需验证全部通过后才标记为 `Completed`。

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
  → Docs KB + Live Source (current runtime)
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
- **P1/P2:** 本仓库已有历史能力，保留为未来可选接入；未进入本次 runtime。

Credentials 不进入仓库、日志、structured findings 或持久化 review result。外部工具失败必须映射为可诊断 failure，不能被当作 zero findings。

## Knowledge strategy

每次 review 绑定 `base_sha`、`head_sha` 和目标 ArkUI repository revision。知识获取顺序是：

1. 读取 changed diff 与修改函数上下文；
2. 用 Docs KB / `kb_search` 获取架构和领域规则；
3. 用 Git、filesystem、`rg` 核实目标 revision 的真实源码；
4. 对每条 finding 保留可复核 evidence。P1/P2 的按需查询是未来显式接入 optional provider 时的扩展，不属于当前 runtime。

Live Source 是当前源码事实的最终 source of truth。Docs KB + Live Source 可独立完成 review。若未来配置 P1/P2，只有在 revision 对齐或兼容语义明确时才能支持 current-fact claim；否则排除该 claim。

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

- **Status:** Completed
- **Scope:** configurable polling/repository/author whitelist；full review identity dedup；JSON/SQLite state；manual/daily knowledge refresh。
- **Acceptance:** `list → filter → dedup → prepare → review → publish → persist` 可运行；`knowledge update/status` 可用；每日检查 repository、Docs KB revision 和 Live Source；P1/P2 不进入 M5 runtime 配置或 refresh。
- **Validation:** 候选 review 在独立 detached runtime worktree 准备目标 head revision，主 ArkUI worktree 不切换 HEAD；Docs KB、Live Source 和 Agent 使用 prepared root，结束后清理。本轮 M5 targeted tests 为 25 passed、0 failed。用户确认 `muil793608902/arkui-review-test#1` 首次 poll 发现并发布 comment `8cf647c450d12e0eb4703c954a702c30ba7f3bac`，相同 identity 的第二次 poll 被 dedup，未重复发布。

### M6 — Demo Validation / Hardening

- **Status:** Completed
- **Scope:** 只验证并修复真实 MVP 闭环。
- **Acceptance:** manual/poll trigger、whitelist、interval、相同完整 identity 跳过、head/base/policy 任一变化后的重新 review、manual knowledge update、当前 Docs KB + Live Source degradation 语义和 GitCode comment 均有验证证据。完整 identity 为 `repository + pr_id + base_sha + head_sha + review_policy_version`；P1/P2 不作为 M6 runtime 验收依赖。
- **Validation:** 本轮修改的 targeted tests 为 44 passed、0 failed。真实 `muil793608902/arkui-review-test#1` 手动 Codex review 在 detached worktree 返回 degraded zero findings，主 checkout HEAD 未变且 runtime worktree 已清理；显式 manual publish 成功，评论含目标 head 与降级状态，无 token/prompt/trace 泄漏。真实 `poll --once` 验证 whitelist `discovered=1, filtered=1`、相同完整 identity `deduplicated=1`。测试 PR 最小 commit 将 head 从 `8f42b31c71eba695f67fac67b047b4612d4e75f8` 更新至 `24f3c4aba62452443efc79b86f8fd35e2f78ca0c` 后，poll 完成新 review、publish 与 SQLite completed 记录，重复 poll 再次 dedup；base/policy 变化由 targeted tests 覆盖。`--interval 2` 连续两轮 poll 验证短间隔配置。真实 ArkUI Git sparse checkout 上 `knowledge status/update` 与 Docs KB 查询成功，Docs KB/Live Source 均 ready；测试 PR 缺 Docs KB 时 degraded review 成功。

## Acceptance Criteria

Fast-MVP 完成必须同时满足：

1. 能手动 review 单个真实 GitCode PR。
2. 可配置 polling interval、repository 与 author whitelist。
3. 同一完整 review identity 不重复 review；base、head 或 policy version 变化可重新 review。
4. 非交互 Codex 产生通过 schema 校验的 structured result。
5. 三类 review 使用与目标 revision 对齐的源码证据；zero findings 合法且与 failure 区分。
6. Review 结果可发布为 GitCode PR summary comment，成功发布后才持久化 reviewed identity。
7. `arkui-review knowledge update/status` 与每日 refresh 可用。
8. 当前 Fast-MVP runtime 使用 ArkUI Review Skill、Docs KB / `kb_search.py` 与 Git / `rg` / filesystem Live Source；Docs KB unavailable/error 时报告 degraded，Live Source 无法对齐 head revision 时失败。P1/P2 不作为当前 runtime 验收依赖。
9. P1/P2/P3/R0 已实现 contract、fixtures 和 baseline 未被追溯改写。

## Degraded behavior

- P1/P2 当前不进入 Fast-MVP runtime；历史 optional provider contract 保留，不纳入 M6 degradation smoke。
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

演示必须至少显示一个真实 PR、所用 base/head SHA、knowledge/degradation 状态、结构化结果、已发布 summary comment，以及相同完整 identity 重复触发未产生第二次 review；head、base 或 policy version 变化应触发重新 review。

## Final validation summary

| 验收项 | 结果 |
| --- | --- |
| M5 targeted tests | 25 passed，0 failed |
| M6 targeted tests | 44 passed，0 failed |
| Real GitCode manual review / publish | Passed；`muil793608902/arkui-review-test#1` detached head review、structured zero findings、显式 comment 发布 |
| Real polling / author whitelist | Passed；允许作者触发检视，不在 whitelist 的作者 `discovered=1, filtered=1`，无发布 |
| Poll interval | Passed；`--interval 2` 连续两轮真实 poll |
| Full identity dedup | Passed；相同 `repository + pr_id + base_sha + head_sha + review_policy_version` 跳过 Agent 与发布；base/policy 变化由 targeted tests 覆盖 |
| New-head re-review / SQLite persistence | Passed；测试 PR 新 head `24f3c4aba62452443efc79b86f8fd35e2f78ca0c` 完成 review、publish 和新的 completed state，重复轮询被跳过 |
| ArkUI knowledge status / update | Passed；真实 ArkUI Git checkout 上 Docs KB 与 Live Source ready，Docs KB 查询返回 evidence |
| Docs KB unavailable degradation | Passed；测试 PR 缺 Docs KB 时报告 unavailable/degraded，Live Source ready，Codex 成功返回 zero findings |
| Published comment content | Passed；含目标 head 与 degradation 状态，无 token、prompt 或 trace 泄漏 |

未运行 strict full suite 或真实 ArkUI baseline；这两项不属于本轮自动验证。

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
