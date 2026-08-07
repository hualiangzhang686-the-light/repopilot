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

## Day 4: Denied Capability and Process Timeout

- Scenario: the harness requests delete or external access, or an allowlisted process exceeds its wall-clock limit.
- Expected: delete/external actions are denied before execution; the process is terminated with `timed_out=true`.
- Reproduction: `python examples/run_day4_harness_demo.py` and `python -m unittest tests.test_day4 -v`.
- Evidence: `traces/day4-permission-denied.jsonl` and `traces/day4-session-success.jsonl`.

### Remaining Day 4 boundary

- This is a local capability gate and subprocess boundary, not an OS container or production sandbox.
- Session JSON is local and unencrypted; it must not contain credentials.

## Day 5: Patch Applied but Verification Fails

- Scenario: a focused patch is applied in the sandbox, but its post-test still exits non-zero.
- Expected: Reviewer returns `REVISE_ONCE`, result status is `failed`, and the original repository remains byte-for-byte unchanged.
- Reproduction: `python -m repopilot fix examples/fix_repo --issue examples/fix_issues/04-test-fails.md --trace traces/day5-fix-failure.jsonl`.
- Evidence: `traces/day5-fix-success.jsonl` and `traces/day5-fix-failure.jsonl`.

### Remaining Day 5 boundary

- Patch generation is a structured exact replacement, not an LLM-generated semantic patch.
- The disposable directory is filesystem isolation, not a container or hostile-code sandbox.

## Day 6: mini-swe-agent Baseline Blocked

- Scenario: install and run mini-swe-agent 2.3.0 for three controlled tasks.
- Actual: the temporary Python 3.14 installation exceeded 240 seconds, and no supported remote-model credential was present.
- Result: baseline status is `blocked_no_model_credentials`; result list stays empty and no comparative metric is claimed.
- Evidence: `eval/mini_swe_baseline.json`, `EVAL_REPORT.md`, and `traces/day6-eval.jsonl`.

The RepoPilot fixed suite itself completed 20/20; this does not satisfy the separate mini-swe-agent comparison acceptance item.

## Day 7: External Validation Boundaries

- OpenAI adapter: implemented and tested with an injected transport; no `OPENAI_API_KEY` was available, so no live request, billing, latency, or model-quality result is claimed.
- DeepSeek adapter: injected-transport tests pass, and a live `deepseek-v4-flash` demo completed search, read, and independently validated citation output on 2026-08-08. Billing and broader model-quality evaluation remain unverified.
- Public repository: direct shallow clone of PyPA sampleproject failed because github.com port 443 was unavailable through the configured proxy. A source-pinned public file was retrieved through the GitHub connector and successfully researched; full-repository validation remains incomplete.
- Docker: Docker Desktop 29.4.2 started, but the first base-image download ended with `unexpected EOF` and the bounded retry timed out after 304 seconds. The Dockerfile is present; image execution remains unverified.
- GitHub Actions: the workflow definition is present; its actual result must be recorded after remote push.
