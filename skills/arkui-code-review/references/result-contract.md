# Review result contract

Return findings only after revision alignment and required tool use succeed. The
Review Service owns repository/PR/revision identity and knowledge provider state.

Agent output:

```json
{
  "findings": []
}
```

Do not return `repository`, `pr_id`, `base_sha`, `head_sha`, `degraded`, or
`provider_statuses`. The service copies those deterministic facts from the review
request and knowledge preflight when it assembles the final `ReviewResult`.

An empty `findings` array means the review completed without enough evidence for a defect. It is not a substitute for a failed tool call, revision mismatch, or invalid output.

Each finding must contain:

- changed file and one-based line;
- category: `stability`, `memory_resource_lifetime`, or `functional_correctness`;
- severity: `critical`, `high`, `medium`, or `low`;
- concise title;
- evidence references with provider, revision, repository-relative source, and locator;
- explanation connecting the current code to the failure mode;
- actionable recommendation;
- confidence from 0 to 1.

At least one evidence reference must be `live_source` at head SHA. Docs KB may support architectural context. P1/P2 evidence is usable only when its provider is ready at head SHA. Do not report style preferences, speculative risks, or issues outside changed behavior.
