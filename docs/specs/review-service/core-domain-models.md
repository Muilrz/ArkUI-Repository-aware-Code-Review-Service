# Code Review Service Core Domain Models

## Scope

本文定义 R0-B 已实现的平台无关 value objects 与 canonical serialization。模型均为 frozen dataclass；它们不包含 GitCode schema、provider query、review reasoning、job lifecycle、storage 或 transport behavior。

## ReviewIdentity

Review identity 的完整字段为：

```text
repository + pr_id + head_sha + review_policy_version
```

四个值均为 trim 后的非空字符串。Equality/hash 使用全部字段。Canonical JSON 使用 UTF-8-compatible JSON、key lexicographic ordering、无非必要空白；反序列化拒绝 missing 和 unknown fields。

## SourceRange and ChangeRef

`SourceRange` 使用一基 line 和可选的零基 column：

```text
start_line
end_line
start_column?
end_column?
```

结束位置不得早于开始位置。`ChangeRef` 记录 file 以及 optional old/new range；至少存在一侧。它不猜测 symbol identity。

## ReviewRequest

`ReviewRequest` 包含：

```text
identity
base_sha
diff
changed_files
changes
```

`identity.head_sha` 是目标 head revision。`base_sha`、`diff` 和 `changed_files` 不得为空；changed files 不重复；至少包含一个 `ChangeRef`，且每个 ref 的 file 必须出现在 `changed_files`。所有 collection 输入必须是有序 sequence，不接受 set/generator，以保证 canonical serialization。R0-B 不加入 GitCode metadata、author filter、dedup claim 或 job state。

## Provider references

`ProviderEvidenceRef` 只保存：

```text
provider
revision?
source
locator?
```

它是 evidence 引用而不是 evidence sufficiency 判断。`revision: null` 表示未知，不表示与 head 对齐。

`ProviderStatusRef` 保存 provider、status、revision/version 和 diagnostics。Status vocabulary：

```text
ready
stale
unavailable
refreshing
error
```

R0-B 只冻结 value/serialization；provider freshness policy 与 refresh/degradation orchestration 属于 R2。

## ReviewFinding

必填字段：

```text
file
location
category
severity
title
description
evidence
reasoning
suggestion
confidence
```

Severity 仅允许：

```text
Critical
High
Medium
Low
```

Finding 至少引用一个 `ProviderEvidenceRef`；confidence 是闭区间 `[0, 1]` 的数值。Category 在 R0-B 中是非空字符串，首批 category policy 到 R3 冻结。模型只保证结构完整，不声称已验证 finding 正确性。

## ReviewResultSummary

Summary 保存 identity、非负 finding count、degraded flag 和 provider statuses。Provider name 不重复；存在 non-ready provider 时 `degraded` 必须为 true。完整 findings、job state、timestamps、failure 和 persistence contract 属于 R0-C/R3。

## Failure behavior

每个公开 value object 都提供 `to_dict` / `from_dict` 与 canonical `to_json` / `from_json`。反序列化使用 exact-field contract：missing、unknown、错误类型、非法 enum、空必填字符串、非法 range/confidence 或不一致 nested value 以 `ValueError` 失败。R0-D 可以引入更细 typed error taxonomy，但不能把 invalid input 静默接受。
