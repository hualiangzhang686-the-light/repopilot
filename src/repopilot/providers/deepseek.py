from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable

from repopilot.agent.models import FinalAnswer, ModelDecision, ToolCall
from repopilot.tools.base import ToolDefinition, ToolExchange


Transport = Callable[[dict[str, object]], dict[str, object]]


class DeepSeekChatClient:
    """Small standard-library client for DeepSeek Chat Completions."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("DeepSeek API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def create(self, payload: dict[str, object]) -> dict[str, object]:
        if self.transport is not None:
            return self.transport(payload)
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"DeepSeek API connection failed: {exc.reason}") from exc
        if not isinstance(value, dict):
            raise RuntimeError("DeepSeek API returned a non-object response")
        return value


class DeepSeekChatModel:
    """AgentModel adapter for DeepSeek Chat Completions function calls."""

    DEFAULT_MODEL = "deepseek-v4-pro"

    def __init__(
        self,
        client: DeepSeekChatClient,
        tools: tuple[ToolDefinition, ...],
        *,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.client = client
        self.tools = tools
        self.model = model
        self.total_usage: dict[str, int] = {}

    @classmethod
    def from_environment(
        cls,
        tools: tuple[ToolDefinition, ...],
        *,
        model: str = DEFAULT_MODEL,
        transport: Transport | None = None,
    ) -> "DeepSeekChatModel":
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        return cls(DeepSeekChatClient(key, transport=transport), tools, model=model)

    def decide(self, question: str, history: list[ToolExchange]) -> ModelDecision:
        successful_tools = {item.call.name for item in history if item.observation.ok}
        if "search_code" not in successful_tools:
            tool_choice: object = {"type": "function", "function": {"name": "search_code"}}
        elif "read_file" not in successful_tools:
            tool_choice = {"type": "function", "function": {"name": "read_file"}}
        else:
            tool_choice = "none"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are RepoPilot in read-only research mode. Use search_code first, then read_file for "
                        "the selected exact line range. Call exactly one tool per response. Do not answer without "
                        "grounded repository evidence. Include path, symbol, line range, and evidence id."
                    ),
                },
                {"role": "user", "content": self._prompt(question, history)},
            ],
            "tools": [self._tool(definition) for definition in self.tools],
            "tool_choice": tool_choice,
            "thinking": {"type": "disabled"},
            "stream": False,
        }
        response = self.client.create(payload)
        self._record_usage(response.get("usage"))
        message = self._message(response)
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            if not isinstance(tool_calls, list) or not all(isinstance(call, dict) for call in tool_calls):
                raise RuntimeError("DeepSeek returned invalid tool calls")
            expected_name = tool_choice["function"]["name"] if isinstance(tool_choice, dict) else None
            names = [
                function.get("name") if isinstance((function := call.get("function")), dict) else None
                for call in tool_calls
            ]
            if any(name != expected_name for name in names):
                raise RuntimeError("DeepSeek returned an unexpected parallel tool call")
            # ponytail: execute the first forced read-only action; add batching only if AgentLoop gains parallel history.
            function = tool_calls[0].get("function")
            if not isinstance(function, dict):
                raise RuntimeError("DeepSeek tool call has no function object")
            arguments = function.get("arguments", "{}")
            parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
            if not isinstance(parsed, dict):
                raise RuntimeError("DeepSeek function-call arguments must be an object")
            return ToolCall(
                name=str(function["name"]),
                arguments=parsed,
                call_id=str(tool_calls[0].get("id", "")),
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("DeepSeek returned neither a function call nor output text")
        metadata = self._evidence_metadata(question, history)
        metadata["provider"] = {"name": "deepseek", "model": self.model, "usage": dict(self.total_usage)}
        return FinalAnswer(content, metadata=metadata)

    @staticmethod
    def _message(response: dict[str, object]) -> dict[str, object]:
        choices = response.get("choices", [])
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise RuntimeError("DeepSeek response must contain exactly one choice")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise RuntimeError("DeepSeek response choice has no message object")
        return message

    @staticmethod
    def _prompt(question: str, history: list[ToolExchange]) -> str:
        exchanges = [
            {
                "tool": item.call.name,
                "arguments": item.call.arguments,
                "observation": {
                    "ok": item.observation.ok,
                    "data": item.observation.data,
                    "error": item.observation.error,
                },
            }
            for item in history
        ]
        return f"Question: {question}\nHistory: {json.dumps(exchanges, ensure_ascii=False, default=str)}"

    @staticmethod
    def _tool(definition: ToolDefinition) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": definition.name,
                "description": definition.description,
                "parameters": definition.input_schema,
            },
        }

    def _record_usage(self, usage: object) -> None:
        if not isinstance(usage, dict):
            return
        mapping = {
            "prompt_tokens": "input_tokens",
            "completion_tokens": "output_tokens",
            "total_tokens": "total_tokens",
        }
        for source, target in mapping.items():
            value = usage.get(source)
            if isinstance(value, int):
                self.total_usage[target] = self.total_usage.get(target, 0) + value

    @staticmethod
    def _evidence_metadata(question: str, history: list[ToolExchange]) -> dict[str, object]:
        search = next((item for item in history if item.call.name == "search_code" and item.observation.ok), None)
        read = next((item for item in reversed(history) if item.call.name == "read_file" and item.observation.ok), None)
        if search is None or read is None:
            return {}
        matches = search.observation.data.get("matches", [])
        read_data = read.observation.data
        read_path = str(read_data.get("path", ""))
        read_start = read_data.get("start_line")
        read_end = read_data.get("end_line")
        if not isinstance(matches, list) or not isinstance(read_start, int) or not isinstance(read_end, int):
            return {}
        top = next(
            (
                match
                for match in matches
                if isinstance(match, dict)
                and str(match.get("path")) == read_path
                and read_start <= int(match.get("start_line", 0)) <= int(match.get("end_line", 0)) <= read_end
            ),
            None,
        )
        if top is None:
            return {}
        lines = str(read_data.get("content", "")).splitlines()
        start_line = int(top["start_line"])
        end_line = int(top["end_line"])
        excerpt = "\n".join(lines[start_line - read_start : end_line - read_start + 1])
        evidence = {
            "id": "ev-1",
            "path": str(top["path"]),
            "symbol": str(top["symbol"]),
            "kind": str(top["kind"]),
            "start_line": start_line,
            "end_line": end_line,
            "reason": "Selected by the DeepSeek provider after hybrid retrieval.",
            "excerpt": excerpt,
        }
        claim = {
            "text": "DeepSeek answer grounded in ev-1.",
            "evidence_ids": ["ev-1"],
            "confidence": "provider-supported",
        }
        return {"evidence_ledger": {"question": question, "evidence": [evidence], "claims": [claim]}}
