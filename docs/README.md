# Documentation Map

项目文档按“长期架构 → 已实现规范 → 开发阶段 → 执行计划 → 可执行验证”组织。

| 位置 | 职责 | 权威内容 |
| --- | --- | --- |
| `architecture/technical-roadmap.md` | 长期系统架构 | Fast-MVP 产品定位、依赖方向、核心边界、M0–M6 路线 |
| `architecture/code-review-architecture.md` | 历史专题架构 | 完整 Service/MCP 设计参考，不是当前 MVP DoD |
| `architecture/repository-knowledge-architecture.md` | 历史专题架构 | 完整 provider service 设计参考；MVP 只要求 Docs KB + Live Source |
| `architecture/code-graph-architecture.md` | P2 Code Graph 架构视图 | frozen P2 层次、依赖方向，以及作为 `P2Provider` 的新定位 |
| `specs/` | 当前已实现规范 | API、identity、relation、evidence、状态与失败语义 |
| `exec-plans/phase-map.md` | 工程阶段 | 历史 P/R 路线状态和当前 Fast-MVP M0–M6 Definition of Done |
| `exec-plans/active/` | 当前工作 | milestone 范围、交付物、Acceptance Criteria、状态 |
| `exec-plans/completed/` | 已完成计划 | 已完成范围和简要验收记录 |
| `exec-plans/superseded/` | 被替代计划 | 未完成但已停止的历史路线及其已完成事实 |
| `decisions/` | 架构决定 | 决策背景、选择、后果和 supersession 关系 |
| `evaluation/` | 评估说明 | baseline、指标和跨 milestone 结果 |
| `tests/fixtures/` | 可执行 expected | 与指定源码 revision 绑定的具体预期 |

同一规则只在一个层级完整定义。Architecture 描述未来如何组合能力；spec 描述代码当前已经实现什么；execution plan 不复制完整 contract；历史 baseline/fixture 不因产品路线变化而改写。

## 当前状态

- P0、P1、P2 已完成，计划保存在 `exec-plans/completed/`。
- P1/P2 作为 Fast-MVP optional provider 复用。既有 specs、baseline 和 frozen fixtures 保持不变。
- P3-A～E 已完成，其 `specs/task-change-context/` 与 `evaluation/p3-*` 继续记录已实现行为和验收事实。
- 未完成的旧 P3 计划已标记 `Superseded` 并移至 [`exec-plans/superseded/P3-task-change-context.md`](exec-plans/superseded/P3-task-change-context.md)。P3-F incremental lifecycle、P4 Agent Runtime 和旧 P5 Engineering Agent 路线不再继续。
- R0 Review Service Foundation 已完成，计划保存在 [`exec-plans/completed/R0-review-service-foundation.md`](exec-plans/completed/R0-review-service-foundation.md)。原 R1–R6 路线已被 Fast-MVP 取代；当前 active plan 是 [`exec-plans/active/Fast-MVP-code-review.md`](exec-plans/active/Fast-MVP-code-review.md)，当前实施入口 M0 为 `Not Started`。

## 当前架构入口

最高层 source of truth 是 [`architecture/technical-roadmap.md`](architecture/technical-roadmap.md)。专题文档：

- [`architecture/code-review-architecture.md`](architecture/code-review-architecture.md)：完整 Code Review Service 历史设计参考；
- [`architecture/repository-knowledge-architecture.md`](architecture/repository-knowledge-architecture.md)：完整 provider service 历史设计参考；
- [`architecture/code-graph-architecture.md`](architecture/code-graph-architecture.md)：P2 frozen semantics 与 `P2Provider` 边界；
- [`decisions/ADR-0005-code-review-service-pivot.md`](decisions/ADR-0005-code-review-service-pivot.md)：前一轮 Service/MCP pivot 的历史决定。

核心原则：优先复用 GitCode API/MCP 和非交互 Codex；Live Source 始终按目标 PR revision 提供源码事实；P1/P2 stale 时显式降级或刷新，不阻塞 `Docs KB + Live Source` review；Skill 不承担 polling，后台轮询属于 lightweight service/CLI；当前不自行建设完整 MCP Server。

## 历史规范与验证入口

- 当前 Review Service：[`specs/review-service/README.md`](specs/review-service/README.md)
- P1：`specs/repository-intelligence/`
- P2：[`specs/code-graph/README.md`](specs/code-graph/README.md)
- P3-A～E：[`specs/task-change-context/README.md`](specs/task-change-context/README.md)
- P1/P2 baseline：[`evaluation/p1-retrieval-baseline.md`](evaluation/p1-retrieval-baseline.md)、[`evaluation/p2-code-graph-baseline.md`](evaluation/p2-code-graph-baseline.md)
- P3 已冻结/验收材料：`evaluation/p3-*`

旧 incremental knowledge、完整 Service/MCP 文档和未完成 contract 可以作为历史工作保留，但不得覆盖当前 Fast-MVP architecture，也不得被解释为 M0–M6 的必选平台化实现。
