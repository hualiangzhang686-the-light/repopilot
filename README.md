# RepoPilot — Day 1–3

RepoPilot is a small, evidence-oriented repository research agent. Day 1 provides a typed, read-only Agent Harness; Day 2 adds Python-aware retrieval and independently validated citations; Day 3 turns issue text into a read-only, evidence-linked triage plan.

```text
Question → CodeResearchModel → search_code → AST chunks + keyword/TF-IDF
                                      ↓
                                  read_file
                                      ↓
                        Evidence Ledger → CitationValidator → Answer
```

## Run

Requires Python 3.11+ and has no third-party runtime dependencies.

```powershell
$env:PYTHONPATH="./src"
python -m repopilot research ./examples/demo_repo "Where is the login function implemented?" --trace ./traces/day2-success.jsonl
python -m repopilot triage ./examples/demo_repo --issue ./examples/issues/01-auth-login.md --trace ./traces/day3-success.jsonl
python ./examples/run_invalid_citation_demo.py
python -m unittest discover -s tests -v
```

The research answer includes a real repository path, AST symbol, exact line range, and Evidence Ledger. The CLI validates that ledger against current repository contents before printing it.

## Implemented Boundaries

- Read-only tools and repository-root path enforcement.
- Maximum steps, cooperative total timeout, and repeated-call stopping.
- Python module, class, function, and method AST chunks.
- Deterministic keyword + TF-IDF hybrid retrieval.
- Evidence Ledger with claim-to-evidence links.
- Rejection of missing files, wrong symbols/lines, stale excerpts, and unknown evidence IDs.
- JSONL success and failure traces.
- Structured Goal Contract, unverified hypotheses, risks, stop condition, and per-step verification.
- Explicit blocking with information gaps when an issue is underspecified.
- Triage performs no repository writes.

## Not Yet Claimed

- No remote LLM or neural embedding API has been integrated or tested.
- No non-Python parser is implemented.
- Sparse retrieval passing five fixtures is not production retrieval-quality validation.
- Triage ranks candidate locations; it does not diagnose or fix a root cause.

## Related Knowledge

- Observe → Think → Act → Observe
- Tool schema, Registry, Dispatch, and structured Observation
- Repository boundary and least-capability design
- AST-based structure-aware chunking
- Sparse vector-space retrieval and hybrid ranking
- Evidence grounding, citation validation, and fail-closed output
- Deterministic model doubles and repeatable evaluation fixtures
- Goal Contract, hypothesis/evidence separation, verification-first planning, and safe stopping
