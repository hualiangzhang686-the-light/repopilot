from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.agent.loop import AgentLoop
from repopilot.agent.models import FinalAnswer, ToolCall
from repopilot.harness.permissions import RepositoryBoundary
from repopilot.harness.trace import TraceWriter
from repopilot.tools.base import ToolContext, ToolExchange
from repopilot.tools.filesystem import register_read_tools
from repopilot.tools.registry import ToolRegistry


class BoundaryFailureModel:
    def decide(self, question: str, history: list[ToolExchange]):
        if not history:
            return ToolCall("read_file", {"path": "../../secret.txt"})
        observation = history[-1].observation
        return FinalAnswer(f"越界读取已被拒绝：{observation.error}")


def main() -> int:
    repo = PROJECT_ROOT / "examples" / "demo_repo"
    boundary = RepositoryBoundary(repo)
    registry = ToolRegistry()
    register_read_tools(registry)
    result = AgentLoop(
        model=BoundaryFailureModel(),
        registry=registry,
        context=ToolContext(boundary.root, boundary),
        trace=TraceWriter(PROJECT_ROOT / "traces" / "failure.jsonl"),
    ).run("尝试读取仓库外文件")
    print(result.answer)
    print(f"status={result.status} stop_reason={result.stop_reason} steps={result.steps}")
    return 0 if result.history and not result.history[0].observation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
