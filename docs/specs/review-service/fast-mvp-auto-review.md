# Fast-MVP M5 automatic review lifecycle

M5 单进程轮询使用 `arkui-review poll`（可加 `--once`）。repository、author whitelist、polling interval、policy version、目标 worktree 和 SQLite path 可通过 CLI 或环境配置。缺少 whitelist、token 或目标 worktree 即失败。普通 `review` 命令继续保持 M4 显式 `--publish` 语义。

`FastMvpReviewIdentity` 是 M5 dedup key：`repository + pr_id + base_sha + head_sha + review_policy_version`。这是独立于已冻结 R0 四字段 `ReviewIdentity` 的 Fast-MVP contract。base SHA 变化而 head 不变必须重新 review；policy version 变化亦然。

每轮：list open PR → author filter → summary identity lookup → detail/changed diff → 复核 author 与完整 identity → 再次 lookup → fetch/prepare revision → knowledge preflight → Code Agent review → summary comment publish → SQLite completed record。任何 review/publish failure 不写 completed；publish 成功而 SQLite 写入失败时显式报错，可能需要人工检查已发布评论后再重试。

SQLite 只记录成功的完整 identity、`status=completed`、comment id 和 UTC `reviewed_at`。不实现分布式锁、队列或跨进程 exactly-once。GitCode list 首批最多读取 20 个最近更新的 open PR。

`arkui-review knowledge update/status` 分别执行 Git fetch + status 和只读 status。常驻 poll loop 至少每 24 小时 fetch 并重新探测 Docs KB registry hash 与 Live Source；每个候选 review 前再次 fetch 并验证目标 worktree 的 HEAD 等于 PR head、tracked source clean。M5 不自动 checkout、改写 target source 或建立 index/snapshot：若本地 worktree 尚未由外部流程切到目标 revision，则明确失败，不使用错误 revision。P1/P2 runtime 不参与 refresh。
