from __future__ import annotations

import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.agent.models import FinalAnswer, ToolCall
from repopilot.cli import build_parser, main
from repopilot.providers.deepseek import DeepSeekChatClient, DeepSeekChatModel
from repopilot.tools.base import Observation, ToolDefinition, ToolExchange


TOOL = ToolDefinition("search_code", "search", {"type": "object", "properties": {}, "required": []}, lambda c, a: {})


class DeepSeekProviderTests(unittest.TestCase):
    def test_provider_parses_one_function_call(self) -> None:
        def transport(payload):
            self.assertEqual(payload["model"], "deepseek-v4-pro")
            self.assertEqual(payload["thinking"], {"type": "disabled"})
            self.assertEqual(payload["tools"][0]["function"]["name"], "search_code")
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {"name": "search_code", "arguments": '{"query":"login"}'},
                                }
                            ],
                        }
                    }
                ]
            }

        model = DeepSeekChatModel(DeepSeekChatClient("test-key", transport=transport), (TOOL,))
        decision = model.decide("login", [])
        self.assertIsInstance(decision, ToolCall)
        self.assertEqual(decision.arguments, {"query": "login"})
        self.assertEqual(decision.call_id, "call-1")

    def test_provider_normalizes_usage_and_adds_evidence(self) -> None:
        response = {
            "choices": [{"message": {"role": "assistant", "content": "Grounded answer [ev-1]."}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
        }
        model = DeepSeekChatModel(DeepSeekChatClient("test-key", transport=lambda payload: response), (TOOL,))
        match = {"path": "app/auth.py", "symbol": "login", "kind": "function", "start_line": 10, "end_line": 14}
        history = [
            ToolExchange(ToolCall("search_code", {"query": "login"}), Observation.success({"matches": [match]})),
            ToolExchange(ToolCall("read_file", {"path": "app/auth.py"}), Observation.success({"content": "def login():\n    pass"})),
        ]
        decision = model.decide("login", history)
        self.assertIsInstance(decision, FinalAnswer)
        self.assertIn("evidence_ledger", decision.metadata)
        self.assertEqual(
            decision.metadata["provider"]["usage"],
            {"input_tokens": 12, "output_tokens": 6, "total_tokens": 18},
        )

    def test_provider_rejects_multiple_parallel_tool_calls(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"id": "one", "function": {"name": "search_code", "arguments": "{}"}},
                            {"id": "two", "function": {"name": "search_code", "arguments": "{}"}},
                        ]
                    }
                }
            ]
        }
        model = DeepSeekChatModel(DeepSeekChatClient("test-key", transport=lambda payload: response), (TOOL,))
        with self.assertRaisesRegex(RuntimeError, "exactly one tool call"):
            model.decide("login", [])

    def test_provider_requires_environment_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            DeepSeekChatModel.from_environment((TOOL,))

    def test_cli_reports_missing_deepseek_key_without_traceback(self) -> None:
        output = StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            status = main(
                ["research", str(PROJECT_ROOT / "examples" / "demo_repo"), "login", "--provider", "deepseek"]
            )
        self.assertEqual(status, 2)
        self.assertIn('"status": "provider_configuration_error"', output.getvalue())
        self.assertIn("DeepSeek API key is required", output.getvalue())

    def test_model_override_is_optional(self) -> None:
        args = build_parser().parse_args(["research", ".", "login", "--provider", "deepseek"])
        self.assertIsNone(args.model)
        overridden = build_parser().parse_args(
            ["research", ".", "login", "--provider", "deepseek", "--model", "deepseek-v4-flash"]
        )
        self.assertEqual(overridden.model, "deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()
