from __future__ import annotations

import argparse
import json
from pathlib import Path

from repopilot.agent.loop import AgentLoop
from repopilot.agent.models import CodeResearchModel
from repopilot.agent.stop_conditions import StopController
from repopilot.harness.permissions import RepositoryBoundary
from repopilot.harness.trace import TraceWriter
from repopilot.harness.replay import TraceReplay
from repopilot.fix.engine import FixEngine
from repopilot.evaluation.runner import EvalRunner
from repopilot.retrieval.evidence import CitationValidator, EvidenceLedger
from repopilot.retrieval.context import ContextManager, default_symbol_cache_root
from repopilot.tools.base import ToolContext
from repopilot.tools.code import register_code_tools
from repopilot.tools.filesystem import register_read_tools
from repopilot.tools.registry import ToolRegistry
from repopilot.triage.engine import IssueTriageEngine
from repopilot.providers.deepseek import DeepSeekChatModel
from repopilot.providers.openai import OpenAIResponsesModel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repopilot", description="Research a repository with traceable read tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    research = subparsers.add_parser("research", help="Answer a repository question with read-only tools.")
    research.add_argument("repo", type=Path)
    research.add_argument("question")
    research.add_argument("--trace", type=Path, default=Path("traces/latest.jsonl"))
    research.add_argument("--max-steps", type=int, default=8)
    research.add_argument("--timeout", type=float, default=30.0)
    research.add_argument("--repeat-limit", type=int, default=2)
    research.add_argument("--provider", choices=("local", "openai", "deepseek"), default="local")
    research.add_argument("--model", help="Provider model override; each provider uses its current default when omitted.")
    context = subparsers.add_parser("context", help="Build a budgeted, source-backed symbol context bundle.")
    context.add_argument("repo", type=Path)
    context.add_argument("query")
    context.add_argument("--token-budget", type=int, default=2000)
    context.add_argument("--max-cards", type=int, default=8)
    triage = subparsers.add_parser("triage", help="Produce a read-only, evidence-linked issue plan.")
    triage.add_argument("repo", type=Path)
    triage.add_argument("--issue", type=Path, required=True)
    triage.add_argument("--trace", type=Path, default=Path("traces/triage-latest.jsonl"))
    fix = subparsers.add_parser("fix", help="Apply and verify one structured patch in a disposable sandbox.")
    fix.add_argument("repo", type=Path)
    fix.add_argument("--issue", type=Path, required=True)
    fix.add_argument("--trace", type=Path, default=Path("traces/fix-latest.jsonl"))
    evaluate = subparsers.add_parser("eval", help="Run the fixed 20-task local evaluation suite.")
    evaluate.add_argument("--project-root", type=Path, default=Path("."))
    evaluate.add_argument("--tasks", type=Path, default=Path("eval/tasks.json"))
    evaluate.add_argument("--output", type=Path, default=Path("eval/results.json"))
    evaluate.add_argument("--report", type=Path, default=Path("EVAL_REPORT.md"))
    evaluate.add_argument("--baseline", type=Path, default=Path("eval/mini_swe_baseline.json"))
    evaluate.add_argument("--trace", type=Path, default=Path("traces/day6-eval.jsonl"))
    replay = subparsers.add_parser("replay", help="Validate and print a JSONL trace timeline.")
    replay.add_argument("trace", type=Path)
    return parser


def run_research(args: argparse.Namespace) -> int:
    boundary = RepositoryBoundary(args.repo)
    registry = ToolRegistry()
    register_read_tools(registry)
    register_code_tools(registry)
    context = ToolContext(
        repository_root=boundary.root,
        boundary=boundary,
        symbol_cache_root=default_symbol_cache_root(),
    )
    try:
        if args.provider == "local":
            model = CodeResearchModel()
        elif args.provider == "openai":
            model = OpenAIResponsesModel.from_environment(
                registry.definitions(), model=args.model or "gpt-5.6-sol"
            )
        else:
            model = DeepSeekChatModel.from_environment(
                registry.definitions(), model=args.model or DeepSeekChatModel.DEFAULT_MODEL
            )
    except ValueError as exc:
        print(
            json.dumps(
                {"status": "provider_configuration_error", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    loop = AgentLoop(
        model=model,
        registry=registry,
        context=context,
        stop_controller=StopController(
            max_steps=args.max_steps,
            timeout_seconds=args.timeout,
            repeat_limit=args.repeat_limit,
        ),
        trace=TraceWriter(args.trace),
    )
    result = loop.run(args.question)
    ledger_value = result.metadata.get("evidence_ledger")
    if not isinstance(ledger_value, dict):
        print(json.dumps({"status": "missing_evidence_ledger"}, ensure_ascii=False, indent=2))
        return 2
    ledger = EvidenceLedger.from_dict(ledger_value)
    errors = CitationValidator(boundary).validate(ledger)
    if errors:
        print(json.dumps({"status": "invalid_citation", "errors": errors}, ensure_ascii=False, indent=2))
        return 2
    if result.answer:
        print(result.answer)
    print(json.dumps({"evidence_ledger": ledger_value}, ensure_ascii=False, indent=2))
    print(f"status={result.status} stop_reason={result.stop_reason} steps={result.steps}")
    print(f"trace={result.trace_path}")
    return 0 if result.status == "completed" else 2


def run_context(args: argparse.Namespace) -> int:
    boundary = RepositoryBoundary(args.repo)
    try:
        bundle = ContextManager(boundary.root, default_symbol_cache_root()).assemble(
            args.query,
            token_budget=args.token_budget,
            max_cards=args.max_cards,
        )
    except (RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "context_error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2))
    return 0 if bundle.target else 2


def run_triage(args: argparse.Namespace) -> int:
    issue_text = args.issue.read_text(encoding="utf-8")
    result = IssueTriageEngine(args.repo).triage(issue_text, trace=TraceWriter(args.trace))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    print(f"trace={args.trace}")
    return 0 if result.status == "ready" else 2


def run_fix(args: argparse.Namespace) -> int:
    issue_text = args.issue.read_text(encoding="utf-8")
    result = FixEngine(args.repo).fix(issue_text, trace=TraceWriter(args.trace))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == "completed" else 2


def run_eval(args: argparse.Namespace) -> int:
    runner = EvalRunner(args.project_root)
    trace = TraceWriter(args.trace)
    trace.emit("eval.start", step=0, data={"tasks": str(args.tasks)})
    summary = runner.run(args.tasks)
    runner.write_outputs(summary, args.output, args.report, args.baseline)
    trace.emit(
        "eval.result",
        step=1,
        data={"total": summary.total, "passed": summary.passed, "failed": summary.failed},
    )
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    trace.emit("baseline.status", step=2, data={"system": baseline["system"], "status": baseline["status"]})
    trace.emit("eval.stop", step=3, data={"reason": "complete" if summary.failed == 0 else "task_failure"})
    print(json.dumps({"total": summary.total, "passed": summary.passed, "failed": summary.failed}, indent=2))
    return 0 if summary.failed == 0 else 2


def run_replay(args: argparse.Namespace) -> int:
    for line in TraceReplay(args.trace).timeline():
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "research":
        return run_research(args)
    if args.command == "context":
        return run_context(args)
    if args.command == "triage":
        return run_triage(args)
    if args.command == "fix":
        return run_fix(args)
    if args.command == "eval":
        return run_eval(args)
    if args.command == "replay":
        return run_replay(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
