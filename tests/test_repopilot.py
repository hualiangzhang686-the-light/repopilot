from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.agent.loop import AgentLoop
from repopilot.agent.models import FinalAnswer, ScriptedModel, ToolCall
from repopilot.agent.stop_conditions import StopController
from repopilot.harness.permissions import RepositoryBoundary
from repopilot.harness.trace import TraceWriter
from repopilot.tools.base import ToolContext, ToolDefinition, ToolExchange
from repopilot.tools.filesystem import register_read_tools
from repopilot.tools.registry import ToolRegistry


class SequenceModel:
    def __init__(self, decisions):
        self.decisions = iter(decisions)

    def decide(self, question: str, history: list[ToolExchange]):
        return next(self.decisions)


class RepeatModel:
    def decide(self, question: str, history: list[ToolExchange]):
        return ToolCall("list_files", {"path": "."})


class RepoPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "app" / "auth.py").write_text(
            "def login(username, password):\n    return username == 'demo'\n",
            encoding="utf-8",
        )
        self.boundary = RepositoryBoundary(self.root)
        self.context = ToolContext(self.boundary.root, self.boundary)
        self.registry = ToolRegistry()
        register_read_tools(self.registry)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_loop(self, model, *, stop=None, trace=None, registry=None) -> AgentLoop:
        return AgentLoop(
            model=model,
            registry=registry or self.registry,
            context=self.context,
            stop_controller=stop,
            trace=trace,
        )

    def test_scripted_model_runs_three_tools_and_returns_answer(self) -> None:
        result = self.make_loop(ScriptedModel()).run("登录逻辑在哪个文件？")
        self.assertEqual(result.status, "completed")
        self.assertEqual([item.call.name for item in result.history], ["list_files", "search_text", "read_file"])
        self.assertIn("app/auth.py", result.answer or "")

    def test_registry_adds_tool_without_changing_loop(self) -> None:
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                "ping",
                "Return pong.",
                {"type": "object", "properties": {}, "required": []},
                lambda context, arguments: {"value": "pong"},
            )
        )
        model = SequenceModel([ToolCall("ping", {}), FinalAnswer("done")])
        result = self.make_loop(model, registry=registry).run("ping")
        self.assertTrue(result.history[0].observation.ok)
        self.assertEqual(result.history[0].observation.data["value"], "pong")

    def test_max_steps_stops_loop(self) -> None:
        stop = StopController(max_steps=1, timeout_seconds=10, repeat_limit=10)
        result = self.make_loop(RepeatModel(), stop=stop).run("repeat")
        self.assertEqual(result.stop_reason, "max_steps")
        self.assertEqual(result.steps, 1)

    def test_total_timeout_stops_loop(self) -> None:
        now = [0.0]

        class AdvancingModel:
            def decide(inner_self, question: str, history: list[ToolExchange]):
                now[0] += 2.0
                return ToolCall("list_files", {"path": "."})

        stop = StopController(max_steps=5, timeout_seconds=1, repeat_limit=5, clock=lambda: now[0])
        result = self.make_loop(AdvancingModel(), stop=stop).run("timeout")
        self.assertEqual(result.stop_reason, "timeout")

    def test_tool_exception_becomes_observation(self) -> None:
        registry = ToolRegistry()

        def explode(context, arguments):
            raise RuntimeError("boom")

        registry.register(
            ToolDefinition("explode", "Raise an error.", {"type": "object", "properties": {}, "required": []}, explode)
        )
        model = SequenceModel([ToolCall("explode", {}), FinalAnswer("recovered")])
        result = self.make_loop(model, registry=registry).run("explode")
        self.assertEqual(result.status, "completed")
        self.assertFalse(result.history[0].observation.ok)
        self.assertIn("RuntimeError: boom", result.history[0].observation.error or "")

    def test_repeated_tool_call_is_stopped(self) -> None:
        stop = StopController(max_steps=10, timeout_seconds=10, repeat_limit=2)
        result = self.make_loop(RepeatModel(), stop=stop).run("repeat")
        self.assertEqual(result.stop_reason, "repeated_tool_call")
        self.assertEqual(result.steps, 2)

    def test_repository_boundary_rejects_escape(self) -> None:
        call = ToolCall("read_file", {"path": "../../secret.txt"})
        observation = self.registry.execute(call, self.context)
        self.assertFalse(observation.ok)
        self.assertIn("PermissionError", observation.error or "")

    def test_jsonl_trace_records_decision_boundaries(self) -> None:
        trace_path = self.root / "trace.jsonl"
        result = self.make_loop(ScriptedModel(), trace=TraceWriter(trace_path)).run("登录逻辑在哪个文件？")
        records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        events = [record["event"] for record in records]
        self.assertEqual(result.status, "completed")
        self.assertEqual(events[0], "run.start")
        self.assertEqual(events.count("tool.request"), 3)
        self.assertEqual(events.count("tool.result"), 3)
        self.assertEqual(events[-1], "loop.stop")


if __name__ == "__main__":
    unittest.main()
