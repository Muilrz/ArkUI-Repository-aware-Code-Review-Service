# Code Review Service Package Boundaries

## Status and scope

本文定义 R0-A 已实现的包结构与静态依赖规则。它不定义 Review domain model、application port method、GitCode/Knowledge adapter 或任何运行时 review behavior。

## Package layout

```text
arkui_agent.review_service
├── domain
├── ports
├── application
└── adapters
```

现有 `arkui_agent.repository`、`arkui_agent.graph`、`arkui_agent.context`、`arkui_agent.knowledge` 和 `arkui_agent.retrieval` 保持原位。历史 `arkui_agent.runtime` 不被新 Service 使用，也不因 R0-A 删除。

## Dependency direction

```text
domain ← ports ← application
   ↑        ↑
   └ adapters
```

规则：

1. `domain` 不依赖 application、ports、adapters 或既有 P1/P2/P3 实现包。
2. `ports` 只允许依赖 `domain`。
3. `application` 只允许依赖 `domain` 与 `ports`，不能导入 concrete adapters。
4. `adapters` 可以依赖 `domain` 与 `ports`；具体 adapter 可以在后续 milestone 访问其负责封装的外部或既有实现。
5. 既有 `arkui_agent` packages 不得反向依赖 `arkui_agent.review_service`。
6. Package root 不通过 eager re-export 隐藏跨层依赖。

这些规则由 `tests/unit/review_service/test_package_boundaries.py` 基于 Python AST 检查，覆盖绝对和相对 Python imports，并阻止 domain/ports/application 绕行依赖既有 `arkui_agent.*` packages。测试不宣称验证运行时 plugin loading 或非 Python 依赖。

## Deferred behavior

- R0-B：ReviewIdentity、ReviewRequest、ReviewFinding 和 provider evidence/status value objects。
- R0-C：GitCodeProvider、KnowledgeGateway、ReviewEngine、ResultStore ports 与 job lifecycle。
- R0-D：configuration、typed errors 和 observability foundation。
- R1+：所有 concrete GitCode、Knowledge、Review Engine、MCP、Scheduler 与 Skill behavior。
