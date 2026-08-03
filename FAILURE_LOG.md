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

## Day 3: Insufficient Issue

- Scenario: the issue only says `It is broken.`
- Expected: status is `blocked`; hypotheses and implementation plan remain empty; missing reproduction information is reported.
- Reproduction: `python -m repopilot triage examples/demo_repo --issue examples/issues/03-vague.md --trace traces/day3-insufficient.jsonl`.
- Evidence: `traces/day3-insufficient.jsonl`.

## Current Limits

- Retrieval supports Python source only.
- TF-IDF is deterministic sparse retrieval, not semantic neural embeddings.
- `CodeResearchModel` is a local workflow double, not a remote LLM provider.
- Day 3 triage is candidate generation and planning, not runtime root-cause validation.
