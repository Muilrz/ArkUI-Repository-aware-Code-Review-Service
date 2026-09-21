# Fast-MVP GitCode PR Context and CLI

本文记录 M0/M1 当前已实现的最小 GitCode integration，不改变 R0 `ReviewIdentity`、`ReviewRequest` 或 `GitCodeProvider.load_review` contract。

## REST boundary

`GitCodeRestAdapter` 只实现：

- `GET /api/v5/repos/{owner}/{repo}/pulls`：读取 open PR summary；
- `GET /api/v5/repos/{owner}/{repo}/pulls/{number}`：读取 metadata、author、base/head SHA；
- `GET /api/v5/repos/{owner}/{repo}/pulls/{number}/files`：读取 changed files 与 per-file diff；
- `POST /api/v5/repos/{owner}/{repo}/pulls/{number}/comments`：summary comment write boundary。

Endpoint 和 response fields 依据 GitCode 官方文档：[PR list](https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-pulls/)、[PR detail](https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-pulls-number/)、[PR files](https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-pulls-number-files/) 和 [PR comment](https://docs.gitcode.com/docs/apis/post-api-v-5-repos-owner-repo-pulls-number-comments/)。M1 不提供 issue、release、merge、reviewer、webhook 或 inline-comment behavior。

HTTP transport 是可注入 port-like boundary；production adapter 使用 Python 标准库 `urllib`。非 2xx、network failure、invalid JSON、非预期 response shape 或缺失必需字段均抛 `GitCodeProviderError`，不得构造部分或虚假 context。

## Carriers

`PullRequestSummary` 包含 repository、PR id、title、author、base SHA 和 head SHA。

`PullRequestContext` 额外包含非空、唯一的 changed file paths 与非空 combined diff。它是进入 R0 `ReviewRequest` 之前的平台中立 carrier，不是第二套 ReviewRequest，也不改变 R0 review identity。

Detail response 的 author 取 `user.login`，revision 取 `base.sha` / `head.sha`。Files response 的 path 取 `filename`，兼容官方 schema 中的 `new_path`；diff 取 `patch.diff`，兼容 top-level `diff`。Combined diff 为每个文件补充 `diff --git` header 后按 API 顺序连接。

## Authentication and secret handling

Public read 不要求 token。若环境存在 `GITCODE_TOKEN`，CLI 只将其包装为 R0 `SecretValue` 并在 adapter 最晚使用点作为官方 `access_token` query parameter 发送。Comment write 必须有 token；缺失时在发出 HTTP request 前失败。

Token 不进入 public config、普通字符串/repr、CLI output、异常公开消息、测试 artifact 或 persisted data。HTTP error body 不进入错误原因，避免服务端回显 credential。

## CLI

安装后的入口为：

```text
arkui-review review --repository owner/repo --pr <positive integer> [--show-diff]
```

`--repository` 缺失时读取 `GITCODE_REPOSITORY`。成功输出 repository、PR id、title、author、base/head SHA、changed-files count 和 UTF-8 diff byte size；`--show-diff` 额外输出 combined diff。CLI 只读取并打印 PR context，不运行 Codex review、不发布评论、不轮询、不持久化状态。
