# Code Review Service Specifications

本目录定义 R0 起已经实现的 Code Review Service contract。长期结构以
[Technical Roadmap](../../architecture/technical-roadmap.md) 和
[Code Review Architecture](../../architecture/code-review-architecture.md) 为准；本目录只记录代码当前具备的行为和边界。

| Specification | Milestone | Implemented contract |
| --- | --- | --- |
| [Package boundaries](package-boundaries.md) | R0-A | `review_service` package layers、依赖方向和当前 non-goals |
| [Core domain models](core-domain-models.md) | R0-B | identity、request/change refs、provider refs、finding、result summary 与 canonical serialization |

Application ports、job lifecycle、GitCode、Knowledge、Review Engine、MCP 和 Scheduler 将在对应 milestone 实现后再增加规范，不从 architecture 提前声明为现有能力。
