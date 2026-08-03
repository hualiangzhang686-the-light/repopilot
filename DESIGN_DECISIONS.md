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
