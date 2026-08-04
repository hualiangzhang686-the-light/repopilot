# RepoPilot Evaluation Report

Generated: `2026-08-04T09:19:38.666512+00:00`

Fixed suite result: **20/20 passed** in 0.403s.

| Category | Passed | Total |
|---|---:|---:|
| research | 5 | 5 |
| triage | 5 | 5 |
| fix | 5 | 5 |
| safety | 3 | 3 |
| resilience | 2 | 2 |

Average recorded tool/process calls per task: `1.40`.

Token and cost values are `null` because this run used deterministic local models and no remote API. This is an explicit measurement boundary, not zero token cost.

## mini-swe-agent baseline

Status: **blocked_no_model_credentials**. Planned controlled tasks: fix-01, fix-02, fix-03.

No credential was available on 2026-08-04, and the isolated CLI install attempt timed out after 240 seconds. No baseline success, cost, token, or latency metric is claimed.

The baseline is therefore reproducibly specified but not scored. RepoPilot and mini-swe-agent must use the same remote model and credentials before latency, token, cost, or success comparisons are valid.

## Artifacts

- Machine-readable results: `eval/results.json`
- Fixed task definitions: `eval/tasks.json`
- Baseline contract: `eval/mini_swe_baseline.json`
