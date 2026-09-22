# Fast-MVP ArkUI Knowledge and Review Skill

本文记录 M3 实现的 agent-neutral ArkUI review Skill、knowledge provider facade 与 repository-aware Agent result contract。M3 不包含 GitCode comment publishing、polling、knowledge refresh 或后台状态。

## Skill

`skills/arkui-code-review/SKILL.md` 定义统一工作流，`references/knowledge-tools.md` 与 `references/result-contract.md` 分别记录 provider/freshness 规则和 structured result。Skill 不包含 Codex 命令或 backend 参数，可由 Service 调用的 Agent 或支持 Skill/tool calling 的 Agent 直接使用。

Review 只覆盖 Stability、Memory / Resource / Lifetime 和 Functional Correctness。Diff 与 repository 内容均视为 untrusted data；只有当前 revision Live Source 证据充分时才能产生 finding，zero findings 是合法成功。

## Knowledge boundary

`ReviewKnowledgeProvider` 是最薄 provider port：

```text
probe(repository, revision) -> KnowledgeProviderResult
query(KnowledgeQuery) -> KnowledgeProviderResult
```

每个结果携带 `ProviderStatusRef` 和可用时的 `KnowledgeEvidence`。Evidence 包含 provider、revision、source、locator 与 content；non-ready provider 不得暴露可用 evidence。

`ReviewKnowledgeFacade` 固定组合四个 provider：

- `DocsKbProvider`：调用目标 repository 的 `docs/kb_search.py <term> --detail`，以 `docs/context_registry.json` SHA-256 标识 KB revision；
- `LiveSourceProvider`：每次查询前验证 Git HEAD 等于 review head 且 tracked worktree clean，再通过 `rg` 或 filesystem read 返回证据；
- `P1KnowledgeProvider`：definition/references/callers/callees/symbols/tests 的 optional facade；
- `P2KnowledgeProvider`：ArkUI framework relations 的 optional facade。

Live Source stale/unavailable/error 是 hard failure。Docs KB 非 ready 时可以在 Live Source 足够的情况下 degraded；P1/P2 未配置、stale 或 error 时不返回 evidence，并继续 Docs KB + Live Source。P1/P2 frozen semantics、fixtures 和 baseline 未修改。

## Agent integration and result validation

设置 `--repository-root` 或 `ARKUI_REPO_ROOT` 后，CLI 先将 PR head 准备为独立 detached runtime worktree，再执行 knowledge preflight，并把 backend-neutral `AgentKnowledgeContext` 交给 `CodeAgentRunner`。不提供 repository root 时保留 M2 diff-only behavior。

Codex 是首个验证 adapter，不是 Skill 或 knowledge API 的依赖。其 repository-aware mode 在已验证 worktree 中以 read-only sandbox 运行，并使用 JSONL event trace 验证 Agent 实际执行：

- Docs KB `kb_search.py`；
- `git rev-parse` revision check；
- `rg`/Git/filesystem Live Source inspection。

最终 `ReviewResult` 包含 `degraded` 与 `provider_statuses`。每个 repository-aware finding 至少有一个 `live_source` evidence，revision 必须等于 head SHA；Docs KB evidence revision 必须等于 provider status；non-ready P1/P2 evidence 被拒绝。

## OpenCodeReview decision

以 OpenCodeReview `v1.12.7` Delegation Mode 执行只读 smoke：`delegate preview` 能确定 changed-file scope，`delegate rule` 能解析 per-file rules，且无需 LLM 配置。默认 scope 会排除 Markdown 与 tests，工具本身也不提供 ArkUI Docs KB、revision freshness 或 P1/P2 evidence contract。因此 M3 不接入其 runtime，仅把它保留为未来可选 scope/rule 辅助；它不是 availability gate。
