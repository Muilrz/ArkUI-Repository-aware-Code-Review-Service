# Knowledge tools and freshness

## Required providers

### Docs KB

From the target repository root, prefer:

```text
python docs/kb_search.py <keyword> --detail
```

Choose terms from changed symbols, component names, lifecycle concepts, and affected subsystems. Read routed KB pages when the search result is relevant. Record provider `docs_kb`, its supplied KB revision/version, query, and document path.

If the script or registry is unavailable, report `unavailable` or `error`. Continue only when Live Source and the review policy provide enough evidence; mark the review degraded.

### Live Source

First verify:

```text
git rev-parse HEAD
git status --porcelain --untracked-files=no
```

HEAD must equal the review head SHA and tracked files must be clean. Otherwise stop the review as a revision-alignment failure.

Use `rg`, Git, and filesystem reads to inspect:

- the complete changed function/class;
- definitions and direct users of changed state;
- ownership, cleanup, registration/unregistration, and asynchronous lifetime paths;
- existing tests and neighboring patterns;
- base-to-head behavior when the diff alone is ambiguous.

Every finding must cite at least one `live_source` reference with head SHA, repository-relative path, and line/range or stable locator.

## Optional providers

### P1 Repository Intelligence

Use only when its provider status is `ready` and revision equals head SHA. Available facts may include symbols, definition, references, callers, callees, fixtures, and tests. Empty results are not failures. If stale/unavailable/error, do not use returned facts and continue degraded.

### P2 ArkUI Code Graph

Use only when its provider status is `ready` and revision equals head SHA. Query bounded ArkUI roles, incoming/outgoing framework relations, component membership, or traces only when they answer a concrete review question. If stale/unavailable/error, do not use returned relations and continue degraded.

## Provider reporting

Report one status per configured provider:

```text
provider: docs_kb | live_source | p1 | p2
status: ready | stale | unavailable | refreshing | error
revision: explicit revision/version when known
diagnostics: short operational facts without credentials
```

The result is degraded when any reported provider is non-ready. P1/P2 degradation does not block review. Live Source non-readiness always blocks success.

