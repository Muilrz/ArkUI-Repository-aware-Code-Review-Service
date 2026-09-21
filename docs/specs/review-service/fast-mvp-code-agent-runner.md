# Fast-MVP Code Agent Review Runner

本文记录 M2 已实现的通用 Code Agent 调用边界与首个 Codex backend。它消费 M1 `PullRequestContext`，不改变 GitCode adapter、R0 `ReviewRequest` 或后续 M3 knowledge contract。

## Platform-neutral boundary

`CodeAgentRunner.review(AgentReviewRequest) -> ReviewResult` 是应用层依赖的唯一 Agent port。`AgentReviewRequest` 只包含 repository、PR id、base/head SHA、changed files 和 diff；不包含命令、模型或 backend output 等 Codex 专属字段。

`CodeAgentReviewService` 负责 `PullRequestContext → AgentReviewRequest → CodeAgentRunner → ReviewResult`。增加其他 Code Agent 时新增 adapter 并在 composition root 增加显式 mapping，不修改 GitCode/M1 flow。当前 mapping 只支持 `codex`，其他值明确失败，不自动 fallback。

## Codex adapter

`CodexAgentRunner` 在可注入的 process boundary 后调用非交互 `codex exec`，使用 ephemeral、read-only、ignore-user-config/rules、bounded timeout 和 request-bound JSON output schema；子进程环境明确移除 `GITCODE_TOKEN`。Prompt builder 与 subprocess adapter 分离，M2 prompt 仅允许依据 supplied diff 检查：

- Stability；
- Memory / Resource / Lifetime；
- Functional Correctness。

M2 不读取 target repository、不调用 web、Docs KB、P1/P2 或 Skill。Diff 被视为 untrusted data；只有 diff 本身提供足够证据时才产生 finding。

## Structured result and failure semantics

Agent interchange JSON 只包含 `findings`。每个 finding 必须属于 changed files，并提供 line、category、severity、title、evidence、explanation、recommendation 和 confidence；adapter 继续执行严格的 finding/evidence validation，并转换为既有 `ReviewFinding`。

Repository、PR id、base/head SHA、`degraded` 与 `provider_statuses` 是 service-owned deterministic facts，不由 Agent 输出或推断。Adapter 从 `AgentReviewRequest` 填充 identity：diff-only 固定 provider statuses 为空且 `degraded=false`；repository-aware 完整复用 knowledge preflight 的 statuses 与 degraded 状态，最终组装统一 `ReviewResult`。Agent 输出这些额外字段会因 strict schema/parser 被拒绝。

`findings: []` 是成功完成且没有充分证据 finding。可执行文件不存在、启动失败、timeout、non-zero exit、空 stdout、invalid JSON 或 invalid schema 均抛 `CodeAgentError`，不能转换成 zero findings。stderr 不进入公开错误消息或结构化结果。

## CLI

```text
arkui-review review --repository owner/repo --pr <id> --agent codex
```

该模式获取真实 PR context、运行选定 backend，并向 stdout 输出 canonical `ReviewResult` JSON。本阶段只打印结果，不发布 GitCode comment。
