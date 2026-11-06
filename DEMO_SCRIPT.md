# RepoPilot 3–5 Minute Demo

1. State the problem: coding agents can produce plausible but unsupported answers and patches.
2. Run Research and show `app/auth.py:10-14 (login) [ev-1]` plus the Evidence Ledger.
3. Run Triage on `01-auth-login.md`; point out Goal Contract, unverified hypotheses, risks, and stop condition.
4. Run Fix on `01-add.md`; show failing pre-test, patch, passing post-test, unified diff, and Reviewer PASS.
5. Run Fix on `04-test-fails.md`; show that a patch with a failed test is not reported as success.
6. Replay `traces/day5-fix-success.jsonl`.
7. Run the fixed Eval and show 20/20 plus the unscored mini-swe-agent boundary.
8. Close with current limits: OpenAI has no live test; DeepSeek has two bounded `deepseek-v4-flash` research demos on `examples/demo_repo`, including the versioned symbol-card path, not a quality or latency benchmark; the local sandbox is not container-grade, and no video artifact is generated automatically.

This file is the verified demo script. A recorded video remains a separate manual deliverable.
