# Architecture

## Research flow

```text
CLI → RepositoryBoundary → ToolRegistry → AgentLoop
    → Model (local, OpenAI Responses, or DeepSeek Chat adapter)
    → search_code → PythonAstChunker → HybridRetriever
    → read_file → Evidence Ledger → CitationValidator → answer
```

The Model proposes `ToolCall` or `FinalAnswer`. The Harness owns execution, permission, stopping, observation, and Trace. This keeps an untrusted or faulty model from directly invoking Python or filesystem APIs.

## Triage flow

```text
Issue → sufficiency check → AST retrieval → candidate evidence
      → unverified hypotheses → Goal Contract → verification-bearing plan
```

Triage is deterministic and read-only. Retrieval relevance creates a candidate, never a confirmed cause.

## Fix flow

```text
Issue fix contract → Triage evidence → SandboxWorkspace(copy)
  → pre-test → exact patch → post-test → unified diff → Reviewer
  → PASS | REVISE_ONCE-and-stop
```

The source repository is never mutated. `PermissionGate` checks the write target, and `CommandRunner` executes a narrow Python allowlist without a shell and with a wall-clock timeout.

## State and observability

- `SessionStore` atomically saves goal, evidence, plan, key state, and summary.
- `ContextCompactor` shortens history without deleting the control contract.
- `ArtifactStore` moves large output out of the inline context and records SHA-256.
- `TraceWriter` writes JSONL decision boundaries; `TraceReplay` validates and prints them.
- `EvalRunner` executes the fixed 20-task suite and generates both JSON and Markdown results.
