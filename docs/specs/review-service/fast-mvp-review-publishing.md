# Fast-MVP GitCode Review Publishing

本文记录 M4 的 Markdown summary formatter 与 GitCode comment 发布行为。M4 不包含 inline comment、approve/request-changes、merge、polling、dedup 或 knowledge refresh。

## Formatter

`format_review_summary(ReviewResult) -> str` 是平台 API 无关的纯 formatter。它输出 review head SHA、简洁 provider status、degraded 标志和 findings。每条 finding 展示 category、severity、file/line range、explanation、evidence 与 recommendation；不会发布 provider diagnostics、Agent trace、prompt 或 credential。

成功的 zero-findings result 输出“没有发现具有足够证据的问题”，并明确这不保证代码没有缺陷。它不把 zero findings 转换成 failure，也不作无证据的安全性声明。

## Publishing boundary

`SummaryCommentPublisher.post_summary_comment(pr_id, body) -> comment_id` 是最小 write port。`ReviewPublishingService` 先格式化 validated `ReviewResult`，再复用 `GitCodeRestAdapter.post_summary_comment` 发布一个 PR summary comment。只有 HTTP 2xx 且 GitCode 返回有效 comment id 才报告 published；configuration、network、HTTP 或 response failure 向调用者传播，不转成 review success。

Token 只通过既有 `SecretValue`/`GITCODE_TOKEN` boundary 到达 GitCode adapter，不进入 formatter、comment body、stdout、异常 public message 或 result。

## CLI safety

默认 Agent review 仍只向 stdout 输出 structured `ReviewResult`：

```text
arkui-review review --repository owner/repo --pr <id> --agent codex
```

真实写操作必须显式增加 `--publish`：

```text
arkui-review review --repository owner/repo --pr <id> --agent codex --publish
```

`--publish` 必须与 `--agent` 同时使用。发布成功后 CLI 才输出 comment id；发布失败返回 non-zero，且不先打印可被误解为完整闭环成功的 ReviewResult。
