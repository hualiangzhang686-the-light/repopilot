from __future__ import annotations

import argparse
import json
from pathlib import Path

from repopilot.agent.loop import AgentLoop
from repopilot.agent.models import CodeResearchModel
from repopilot.agent.stop_conditions import StopController
from repopilot.harness.permissions import RepositoryBoundary
from repopilot.harness.trace import TraceWriter
from repopilot.fix.engine import FixEngine
from repopilot.retrieval.evidence import CitationValidator, EvidenceLedger
from repopilot.tools.base import ToolContext
from repopilot.tools.code import register_code_tools
from repopilot.tools.filesystem import register_read_tools
from repopilot.tools.registry import ToolRegistry
from repopilot.triage.engine import IssueTriageEngine


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
    triage = subparsers.add_parser("triage", help="Produce a read-only, evidence-linked issue plan.")
    triage.add_argument("repo", type=Path)
    triage.add_argument("--issue", type=Path, required=True)
    triage.add_argument("--trace", type=Path, default=Path("traces/triage-latest.jsonl"))
    fix = subparsers.add_parser("fix", help="Apply and verify one structured patch in a disposable sandbox.")
    fix.add_argument("repo", type=Path)
    fix.add_argument("--issue", type=Path, required=True)
    fix.add_argument("--trace", type=Path, default=Path("traces/fix-latest.jsonl"))
    return parser


def run_research(args: argparse.Namespace) -> int:
    boundary = RepositoryBoundary(args.repo)
    registry = ToolRegistry()
    register_read_tools(registry)
    register_code_tools(registry)
    context = ToolContext(repository_root=boundary.root, boundary=boundary)
    loop = AgentLoop(
        model=CodeResearchModel(),
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
    if isinstance(ledger_value, dict):
        ledger = EvidenceLedger.from_dict(ledger_value)
        errors = CitationValidator(boundary).validate(ledger)
        if errors:
            print(json.dumps({"status": "invalid_citation", "errors": errors}, ensure_ascii=False, indent=2))
            return 2
    if result.answer:
        print(result.answer)
    if isinstance(ledger_value, dict):
        print(json.dumps({"evidence_ledger": ledger_value}, ensure_ascii=False, indent=2))
    print(f"status={result.status} stop_reason={result.stop_reason} steps={result.steps}")
    print(f"trace={result.trace_path}")
    return 0 if result.status == "completed" else 2


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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "research":
        return run_research(args)
    if args.command == "triage":
        return run_triage(args)
    if args.command == "fix":
        return run_fix(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
