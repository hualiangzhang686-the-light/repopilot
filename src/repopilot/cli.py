from __future__ import annotations

import argparse
from pathlib import Path

from repopilot.agent.loop import AgentLoop
from repopilot.agent.models import ScriptedModel
from repopilot.agent.stop_conditions import StopController
from repopilot.harness.permissions import RepositoryBoundary
from repopilot.harness.trace import TraceWriter
from repopilot.tools.base import ToolContext
from repopilot.tools.filesystem import register_read_tools
from repopilot.tools.registry import ToolRegistry


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
    return parser


def run_research(args: argparse.Namespace) -> int:
    boundary = RepositoryBoundary(args.repo)
    registry = ToolRegistry()
    register_read_tools(registry)
    context = ToolContext(repository_root=boundary.root, boundary=boundary)
    loop = AgentLoop(
        model=ScriptedModel(),
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
    if result.answer:
        print(result.answer)
    print(f"status={result.status} stop_reason={result.stop_reason} steps={result.steps}")
    print(f"trace={result.trace_path}")
    return 0 if result.status == "completed" else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "research":
        return run_research(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
