# Design Decisions

## Day 1: Small Harness Loop

The Agent Loop only requests a model decision, dispatches typed tool calls, returns structured observations, and enforces stop conditions. Path resolution, file reads, and trace serialization stay outside the loop.

The first version exposes `list_files`, `search_text`, and `read_file` rather than arbitrary shell access. A deterministic `ScriptedModel` tests Harness mechanics without claiming real LLM reasoning quality.

## Day 2: AST Chunks Before Retrieval

Python definitions are indexed as exact file, symbol, kind, start line, end line, and source text. Module chunks provide fallback context, while function, method, and class chunks provide precise citations.

Retrieval combines lexical overlap with a standard-library TF-IDF vector-space cosine score. This is deterministic and dependency-free; it is deliberately documented as sparse retrieval, not a neural embedding model.

## Day 2: Evidence Is Validated Outside the Model

`CodeResearchModel` proposes a claim and Evidence Ledger. `CitationValidator` then independently checks repository boundaries, file existence, AST symbol/line identity, excerpt contents, unique evidence IDs, and claim-to-evidence references. A fabricated citation cannot become a final CLI answer merely because the model emitted it.

## Day 3: Triage Is a Read-Only Decision Product

`IssueTriageEngine` produces a Goal Contract, candidate evidence, explicitly unverified hypotheses, verification-bearing plan steps, risks, information gaps, and a stop condition. Retrieval rank creates candidates only; even the first result is never labeled a root cause.

Triage has no write tool or mutation path. A vague issue returns `blocked`, emits a failure trace, and requests reproduction details instead of inventing an implementation plan.

## Day 4: Capabilities Are Denied Centrally

`PermissionGate` classifies read, write, execute, delete, and external capabilities. Read is allowed inside the existing repository boundary; write requires an explicit target inside a sandbox; execute requires an argument-vector prefix allowlist; delete and external actions are disabled. Commands never use a shell.

Session state stores the goal, evidence, plan, key state, and compacted history separately so compaction cannot accidentally discard the control contract. Large output is replaced inline by a bounded preview and an integrity-linked Artifact. Process timeout and consecutive failed observations are separate stop mechanisms.

## Day 5: Patch Only in a Disposable Copy

`FixEngine` parses one explicit patch contract from the issue, requires Triage evidence for the target path, copies the repository into a disposable sandbox, records a pre-test, applies one exact text replacement, records a post-test, creates a unified diff, and gives the evidence to a non-mutating Reviewer. Only a non-empty diff with a passing post-test is `completed`.

The test command is not free-form shell: it must be `{python} -c ...` or `{python} -m unittest ...`, executes without a shell, and has a process timeout. A failed review emits `REVISE_ONCE` but the deterministic version stops at the one-revision limit rather than inventing a second patch.

## Day 6: Fixed Tasks and Machine-Generated Metrics

The 20-task suite is stored as data with an expected result for every task. One runner dispatches the five required categories and records actual output, pass/fail, latency, tool/process calls, citation validity, and failure layer. Token and cost remain `null` when no remote model ran; they are not reported as zero.

The mini-swe-agent comparison has a pinned version, three shared tasks, repository, timeout, model-equality rule, cost limit, and test contract. Because no model credential was available and the isolated install timed out, the report marks it blocked and leaves results empty rather than fabricating a baseline.

## Day 7: Provider Is an Adapter, Evidence Is Still a Harness Rule

The OpenAI Responses API adapter translates RepoPilot Tool Definitions into function tools and translates response items back into `ToolCall` or `FinalAnswer`. The transport is injectable for deterministic tests. Remote answers still require a locally reconstructed Evidence Ledger and the same independent citation validation as the local model.

Trace replay, Docker, CI, and delivery documents expose existing behavior rather than adding hidden autonomy. The default model follows the official 2026-08-04 resolver result (`gpt-5.6-sol`), but no live call is claimed without an API key.
