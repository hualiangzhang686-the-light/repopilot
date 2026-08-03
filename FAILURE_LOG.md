# Failure Log

## Day 1: Repository Escape

- Scenario: `read_file` requests `../../secret.txt`.
- Expected: the repository boundary rejects it and the Registry returns a failed Observation.
- Reproduction: `python examples/run_failure_demo.py`.
- Evidence: `traces/failure.jsonl`.

## Day 2: Fabricated Citation

- Scenario: a claim cites `app/missing.py:1-2` and symbol `missing`.
- Expected: citation validation fails before the answer is accepted.
- Reproduction: `python examples/run_invalid_citation_demo.py`.
- Evidence: `traces/day2-invalid-citation.jsonl`.

## Current Limits

- Retrieval supports Python source only.
- TF-IDF is deterministic sparse retrieval, not semantic neural embeddings.
- `CodeResearchModel` is a local workflow double, not a remote LLM provider.
