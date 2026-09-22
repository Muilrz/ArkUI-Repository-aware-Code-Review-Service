# Code Review Service Specifications

本目录定义 R0 起已经实现的 Code Review Service contract。长期结构以
[Technical Roadmap](../../architecture/technical-roadmap.md) 和
[Code Review Architecture](../../architecture/code-review-architecture.md) 为准；本目录只记录代码当前具备的行为和边界。

| Specification | Milestone | Implemented contract |
| --- | --- | --- |
| [Package boundaries](package-boundaries.md) | R0-A | `review_service` package layers、依赖方向和当前 non-goals |
| [Core domain models](core-domain-models.md) | R0-B | identity、request/change refs、provider refs、finding、result summary 与 canonical serialization |
| [Application ports and job lifecycle](application-ports-and-job-lifecycle.md) | R0-C | four ports、minimal knowledge carrier、job state/failure 与 synchronous orchestration |
| [Foundation configuration, errors and observability](foundation-configuration-errors-observability.md) | R0-D | safe config/secret boundary、unified failure taxonomy、correlation 与 structured diagnostics |
| [R0 foundation traceability](r0-traceability.md) | R0-D | Phase Map R0 Definition of Done 的 spec/implementation/test evidence |
| [Fast-MVP GitCode PR context and CLI](fast-mvp-gitcode-cli.md) | M0/M1 | GitCode REST read/comment boundary、PR carrier、CLI 与失败语义 |
| [Fast-MVP Code Agent Review Runner](fast-mvp-code-agent-runner.md) | M2 | 通用 Agent port、Codex backend、structured `ReviewResult` 与失败语义 |
| [Fast-MVP ArkUI Knowledge and Review Skill](fast-mvp-knowledge-skill.md) | M3/M6 | agent-neutral Skill、revision-bound providers、当前 runtime 的 degraded behavior 与 evidence validation |
| [Fast-MVP GitCode Review Publishing](fast-mvp-review-publishing.md) | M4 | Markdown summary formatter、显式 publish opt-in 与 comment failure semantics |
| [Fast-MVP Automatic Review Lifecycle](fast-mvp-auto-review.md) | M5/M6 | full identity dedup、polling、SQLite completed state，以及自动与手动 review 的 Git revision preparation |

Fast-MVP M0–M6 已完成：GitCode boundary、Code Agent runner、Docs KB + Live Source/Skill、summary publishing、单进程 polling、SQLite 完整 identity dedup、detached revision preparation 和最小 Git/Docs KB refresh 均已实现并验收。完整 MCP、分布式 scheduler 与复杂 repository manager 不属于已实现范围。
