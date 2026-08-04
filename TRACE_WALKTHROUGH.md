# Trace Walkthrough

## Research

`traces/day2-success.jsonl` records `run.start`, model request, `search_code`, `read_file`, final answer, and `loop.stop`. Tool request and result share a `call_id`, so the selected code and final evidence can be reconstructed.

## Permission failure

`traces/day4-permission-denied.jsonl` records delete and external capabilities denied before execution. The denial is a result, not an unhandled exception.

## Fix success and failure

Both Day 5 traces contain:

```text
fix.start → fix.pre_test → fix.patch → fix.post_test → fix.review → fix.stop
```

The success trace ends in `verified_patch`; the failure trace records a non-zero post-test and `review_revision_limit`.

## Evaluation and replay

`traces/day6-eval.jsonl` records the fixed suite result and the blocked mini-swe baseline status. Run:

```powershell
repopilot replay ./traces/day6-eval.jsonl
```

Replay validates every JSONL record and rejects malformed JSON or mixed run IDs. Session recovery is separate from Trace replay: Session holds resumable control state, while Trace is the immutable execution timeline for one saved run file.
