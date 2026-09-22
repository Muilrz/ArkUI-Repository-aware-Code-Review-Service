# Development Phase Map

## 1. Purpose and authority

本文把 [Technical Roadmap](../architecture/technical-roadmap.md) 转换为当前可验收的工程阶段。Roadmap 决定产品方向和架构边界；本文件决定阶段与 Definition of Done；`active/` execution plan 决定当前 milestone 的具体范围。

**Fast-MVP — GitCode ArkUI Automated Code Review** 已完成 M0–M6。P0/P1/P2、P3-A～E 和 R0 已完成能力保持历史状态；原完整自研 R0–R6 路线不再作为执行顺序，R1–R6 被 Fast-MVP 取代。下一阶段尚未定义。

## 2. Global principles

- 优先复用现成 GitCode API/MCP、Codex CLI 和经 smoke 验证的外部工具，不自行开发完整 MCP Server。
- 不建设 generic Agent Runtime。自动 polling、author filter、full identity dedup、knowledge refresh 和 state persistence 属于 lightweight service/CLI。
- Docs KB + Live Source 是最低可用知识路径；Live Source 对目标 repository revision 的源码事实具有最终权威。
- P1/P2 是架构上的 optional enhancement，当前 Fast-MVP runtime 不配置；若未来接入，stale、unavailable 或 refresh failure 不得阻塞 review，也不得被当作当前 revision 的确定事实。
- Review 只在有足够源码证据时产生 finding；zero findings 是合法成功结果，且必须与 Agent failure 区分。
- 阶段只实现 MVP 闭环所需能力，不以长期平台化要求扩大 scope。

## 3. Historical phases and superseded routes

| Phase / route | Status | Continuing role |
| --- | --- | --- |
| P0 — Engineering Foundation | Completed | 工程、配置、测试和可观测基础可复用 |
| P1 — Repository Intelligence | Completed | 未来 optional P1 provider；当前 runtime 不接入；保留 frozen contracts/fixtures/baseline |
| P2 — ArkUI Code Graph | Completed | 未来 optional P2 provider；当前 runtime 不接入；保留 frozen semantics/fixtures/baseline |
| P3-A～E — Task / Change Context contracts | Completed milestones in a superseded phase | 已实现 contract 保留并可选择性复用 |
| P3 remaining route | Superseded | 不继续 P3-F incremental lifecycle/G/H/I |
| P4/P5 old route | Superseded before execution | 不建设 Agent Runtime 或旧 Agent/UT capability |
| R0 — Review Service Foundation | Completed; route superseded | 已实现 foundation/specs 保留，可由 MVP 复用 |
| R1–R6 complete Service/MCP route | Superseded by Fast-MVP route | 未完成阶段不继续、不标记 Completed |

R0 的 `Completed` 是已验收实现事实；“route superseded”表示它不再通向原定 R1–R6 执行序列。原 R1 计划见 [`superseded/R1-gitcode-integration-review-state.md`](superseded/R1-gitcode-integration-review-state.md)。

## 4. M0 — Fast-MVP Foundation & External Tool Smoke

**Status:** Completed

**Definition of Done:**

1. Codex CLI 可非交互运行并返回可判断的成功/失败结果。
2. GitCode API 或 GitCode MCP 可读取一个真实 PR 的基本信息；若采用 OpenCodeReview，只完成 smoke 与取舍记录。
3. 最小 `arkui-review` CLI/package 骨架和 config boundary 建立。
4. 不实现 Review Engine、完整 MCP Server、scheduler framework 或 P1/P2 refresh integration。

## 5. M1 — GitCode Minimal Integration

**Status:** Completed

**Definition of Done:**

1. 最小 adapter 能获取 open PR、metadata、author、base/head SHA、changed files 和 diff。
2. `arkui-review review --pr <PR_ID>` 能读取并打印绑定真实 head revision 的 PR context。
3. 具备发布 PR summary comment 所需的最小 write boundary，不扩展 issue、release、merge、webhook 或复杂 reviewer 管理。

## 6. M2 — Code Agent Review Runner

**Status:** Completed

**Definition of Done:**

1. PR context 可输入通用 Code Agent boundary；Codex 作为首个已验证 backend，通过非交互调用返回符合明确 JSON schema 的 structured review result。
2. Agent failure、invalid output 与成功 zero findings 有稳定且不同的结果。
3. Runner 保留目标 repository revision 和必要 diagnostics，不要求 inline comment。

## 7. M3 — ArkUI Knowledge & Review Skill

**Status:** Completed

**Definition of Done:**

1. 建立 `skills/arkui-code-review/`，指导 Agent 读取 diff、函数上下文、Docs KB、Live Source，以及按需使用 P1/P2。
2. Stability、Memory / Resource / Lifetime、Functional Correctness 三类 review 有明确证据规则。
3. Docs KB + Live Source 可独立完成 degraded review；stale P1/P2 不会产生当前 revision 的确定 claim。

## 8. M4 — GitCode Review Publishing

**Status:** Completed

**Definition of Done:**

1. Structured findings 可格式化为一个清晰的 GitCode PR summary comment。
2. 每条 finding 包含 file、可确定时的 line、category、severity、evidence、explanation 和 recommendation。
3. 发布失败不记录为成功；zero findings 使用明确的成功摘要。

## 9. M5 — Auto Polling & Knowledge Refresh

**Status:** Completed

**Definition of Done:**

1. 可配置 repository、polling interval 和 author whitelist；流程遵循 `list → filter → full identity dedup → refresh/prepare → review → publish → persist`。
2. 同一 `repository + pr_id + base_sha + head_sha + review_policy_version` 不重复 review；base 或 policy 变化可重新 review。
3. 简单 JSON 或 SQLite state 支持进程重启后的 dedup，不引入 distributed queue infrastructure。
4. `arkui-review knowledge update/status` 可用，并支持每日 repository/Docs KB/Live Source refresh。
5. M5 runtime 不配置或刷新 P1/P2；Docs KB + Live Source 可独立 review。

## 10. M6 — Demo Validation & Hardening

**Status:** Completed

**Definition of Done:**

1. 真实 GitCode PR 可由 manual trigger 或 poll 完成 Codex review、Docs KB + Live Source knowledge retrieval、structured result、GitCode comment 和完整 review identity dedup。
2. author whitelist、polling interval、相同 `repository + pr_id + base_sha + head_sha + review_policy_version` 跳过，以及 head、base 或 policy version 变化后的重新 review 均有验证证据。
3. manual knowledge update 可用；验证当前 runtime 的 Docs KB unavailable/error degradation 与 Live Source revision failure 语义，不把 P1/P2 作为 M6 runtime 前置依赖。
4. 只修复 MVP 闭环的可靠性、安全性与演示阻塞项，不扩展为完整长期平台。

## 11. Dependency and execution rules

Fast-MVP 交付顺序为 `M0 → M1 → M2 → M3 → M4 → M5 → M6`。计划保存在 [`completed/Fast-MVP-code-review.md`](completed/Fast-MVP-code-review.md)，M0–M6 已完成；`active/` 下没有获批准的下一阶段计划。

Status 统一使用 `Not Started`、`In Progress`、`Blocked`、`Completed`、`Superseded`。开始实现时只将所选 milestone 设为 `In Progress`；只有 Acceptance Criteria 与必需验证全部通过才能标记 `Completed`。
