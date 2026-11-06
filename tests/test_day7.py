from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.agent.models import FinalAnswer, ToolCall
from repopilot.cli import main
from repopilot.harness.replay import TraceReplay
from repopilot.harness.trace import TraceWriter
from repopilot.providers.openai import OpenAIResponsesClient, OpenAIResponsesModel
from repopilot.tools.base import Observation, ToolDefinition, ToolExchange


TOOL = ToolDefinition("search_code", "search", {"type": "object", "properties": {}, "required": []}, lambda c, a: {})


class Day7DeliveryTests(unittest.TestCase):
    def test_openai_provider_parses_function_call(self) -> None:
        def transport(payload):
            self.assertEqual(payload["model"], "gpt-5.6-sol")
            return {"output": [{"type": "function_call", "name": "search_code", "arguments": "{\"query\":\"login\"}", "call_id": "call-1"}]}

        model = OpenAIResponsesModel(OpenAIResponsesClient("test-key", transport=transport), (TOOL,))
        decision = model.decide("login", [])
        self.assertIsInstance(decision, ToolCall)
        self.assertEqual(decision.arguments, {"query": "login"})

    def test_openai_provider_preserves_usage_and_evidence(self) -> None:
        response = {
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Grounded answer [ev-1]."}]}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
        model = OpenAIResponsesModel(OpenAIResponsesClient("test-key", transport=lambda payload: response), (TOOL,))
        match = {"path": "app/auth.py", "symbol": "login", "kind": "function", "start_line": 10, "end_line": 14}
        history = [
            ToolExchange(ToolCall("search_code", {"query": "login"}), Observation.success({"matches": [match]})),
            ToolExchange(ToolCall("read_file", {"path": "app/auth.py"}), Observation.success({"content": "def login():\n    pass"})),
        ]
        decision = model.decide("login", history)
        self.assertIsInstance(decision, FinalAnswer)
        self.assertIn("evidence_ledger", decision.metadata)
        self.assertEqual(decision.metadata["provider"]["usage"]["total_tokens"], 15)

    def test_openai_provider_requires_environment_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            OpenAIResponsesModel.from_environment((TOOL,))

    def test_cli_reports_missing_provider_key_without_traceback(self) -> None:
        output = StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            status = main(["research", str(PROJECT_ROOT / "examples" / "demo_repo"), "login", "--provider", "openai"])
        self.assertEqual(status, 2)
        self.assertIn('"status": "provider_configuration_error"', output.getvalue())

    def test_trace_replay_validates_and_formats_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trace.jsonl"
            trace = TraceWriter(path, run_id="run-1")
            trace.emit("run.start", step=0, data={"question": "where"})
            trace.emit("loop.stop", step=1, data={"reason": "done"})
            timeline = TraceReplay(path).timeline()
        self.assertEqual(len(timeline), 2)
        self.assertIn("event=run.start", timeline[0])

    def test_trace_replay_rejects_invalid_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.jsonl"
            path.write_text("not-json\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                TraceReplay(path).records()


if __name__ == "__main__":
    unittest.main()
