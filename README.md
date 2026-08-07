# RepoPilot

RepoPilot is a compact, evidence-oriented Python repository agent. It separates model proposals from Harness execution, binds research claims to real code locations, blocks unsupported issue plans, and applies fixes only in disposable repository copies.

## Why this instead of an unrestricted coding agent?

RepoPilot is designed for experiments where evidence, safety, replay, and evaluation matter more than maximum autonomy. It intentionally exposes narrow typed tools, validates citations outside the model, denies destructive/external capabilities, and refuses to call a patch successful until its focused post-test passes.

## Modes

```text
research  question → search_code → read_file → Evidence Ledger → validated answer
triage    issue → Goal Contract → evidence → unverified hypotheses → verified plan
fix       issue → triage → disposable copy → patch → tests → diff → reviewer
eval      fixed 20-task suite → machine-readable metrics → EVAL_REPORT.md
replay    JSONL trace → validated readable timeline
```

## Five-minute quickstart

Requires Python 3.11+ and has no third-party runtime dependency.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "setuptools>=68"
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation .

repopilot research ./examples/demo_repo "Where is the login function implemented?"
repopilot triage ./examples/demo_repo --issue ./examples/issues/01-auth-login.md
repopilot fix ./examples/fix_repo --issue ./examples/fix_issues/01-add.md
repopilot eval --project-root .
repopilot replay ./traces/day5-fix-success.jsonl
```

Run tests:

```powershell
python -m unittest discover -s tests -v
```

## Research evidence

A local research answer includes the true path, AST symbol, line range, and Evidence ID:

```text
The most relevant implementation is `login` at `app/auth.py:10-14 (login)` [ev-1].
```

`CitationValidator` independently checks the current file, repository boundary, symbol, kind, line range, excerpt, Evidence IDs, and Claim links before CLI output is accepted.

## OpenAI provider

The optional provider adapter uses the OpenAI Responses API with function tools. The current default is `gpt-5.6-sol`; override it explicitly when needed.

```powershell
$env:OPENAI_API_KEY="..."
repopilot research ./examples/demo_repo "Where is login implemented?" --provider openai --model gpt-5.6-sol
```

The adapter and response parsing are unit-tested with an injected transport. No live API call was made for this release because no API key was present. See the official [Responses API guide](https://developers.openai.com/api/docs/guides/responses) and [current model guidance](https://developers.openai.com/api/docs/guides/latest-model).

## DeepSeek provider

The optional DeepSeek adapter uses the official Chat Completions endpoint and function tools. Its current default is `deepseek-v4-pro`; use `deepseek-v4-flash` explicitly when preferred.

```powershell
$env:DEEPSEEK_API_KEY="..."
repopilot research ./examples/demo_repo "Where is login implemented?" --provider deepseek
repopilot research ./examples/demo_repo "Where is login implemented?" --provider deepseek --model deepseek-v4-flash
```

The adapter normalizes DeepSeek token usage to `input_tokens`, `output_tokens`, and `total_tokens`, and the final answer still has to pass RepoPilot's independent citation validator. The provider tests use an injected transport; a live API call requires a user-supplied key.

## Evaluation

`eval/tasks.json` contains exactly 20 tasks with expected results:

| Category | Tasks | Latest local result |
|---|---:|---:|
| Code research | 5 | 5/5 |
| Issue triage | 5 | 5/5 |
| Sandboxed fix | 5 | 5/5 |
| Permission/path safety | 3 | 3/3 |
| Timeout/tool failure | 2 | 2/2 |

The latest deterministic run passed 20/20. Token and cost metrics are `null`, not zero, because no remote provider ran. The mini-swe-agent 2.3.0 comparison contract covers three controlled tasks but remains unscored: no model credential was available and the isolated installation timed out. See [EVAL_REPORT.md](EVAL_REPORT.md).

## Docker

```powershell
docker build -t repopilot:0.8.0 .
docker run --rm repopilot:0.8.0 --help
```

Mount a repository read-only for research. Do not pass API keys into untrusted images or commit them to the repository.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — components and execution flows.
- [SECURITY.md](SECURITY.md) — threat model, enforced controls, and non-goals.
- [TRACE_WALKTHROUGH.md](TRACE_WALKTHROUGH.md) — successful and failed trace timelines.
- [FAILURE_LOG.md](FAILURE_LOG.md) — reproduced failures and current limits.
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) — why each stage was implemented this way.
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — reproducible 3–5 minute demo script.
- [CONTRIBUTIONS.md](CONTRIBUTIONS.md) — contribution and validation expectations.

## Verified boundaries

- Python AST repositories only.
- Local retrieval is keyword + sparse TF-IDF, not neural embeddings.
- `fix` uses exact structured replacements in disposable filesystem copies; it is not an LLM patch generator.
- Test execution is restricted to Python `-c` or `-m unittest`, without a shell.
- The local sandbox is not a container security boundary for hostile code.
- OpenAI and DeepSeek remote execution, mini-swe-agent comparative metrics, video recording, and GitHub Actions status are separate external validations.
