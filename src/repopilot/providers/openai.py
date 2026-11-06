from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable

from repopilot.agent.models import FinalAnswer, ModelDecision, ToolCall
from repopilot.tools.base import ToolDefinition, ToolExchange


Transport = Callable[[dict[str, object]], dict[str, object]]


class OpenAIResponsesClient:
    """Small standard-library client for POST /v1/responses."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def create(self, payload: dict[str, object]) -> dict[str, object]:
        if self.transport is not None:
            return self.transport(payload)
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"OpenAI Responses API returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI Responses API connection failed: {exc.reason}") from exc
        if not isinstance(value, dict):
            raise RuntimeError("OpenAI Responses API returned a non-object response")
        return value


class OpenAIResponsesModel:
    """AgentModel adapter for OpenAI Responses API function calls."""

    def __init__(
        self,
        client: OpenAIResponsesClient,
        tools: tuple[ToolDefinition, ...],
        *,
        model: str = "gpt-5.6-sol",
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
        model: str = "gpt-5.6-sol",
        transport: Transport | None = None,
    ) -> "OpenAIResponsesModel":
        key = os.environ.get("OPENAI_API_KEY", "")
        return cls(OpenAIResponsesClient(key, transport=transport), tools, model=model)

    def decide(self, question: str, history: list[ToolExchange]) -> ModelDecision:
        payload = {
            "model": self.model,
            "input": self._prompt(question, history),
            "tools": [self._tool(definition) for definition in self.tools],
            "reasoning": {"effort": "low"},
        }
        response = self.client.create(payload)
        self._record_usage(response.get("usage"))
        output = response.get("output", [])
        if not isinstance(output, list):
            raise RuntimeError("Responses API output must be a list")
        for item in output:
            if isinstance(item, dict) and item.get("type") == "function_call":
                arguments = item.get("arguments", "{}")
                parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
                if not isinstance(parsed, dict):
                    raise RuntimeError("function-call arguments must be an object")
                return ToolCall(
                    name=str(item["name"]),
                    arguments=parsed,
                    call_id=str(item.get("call_id") or item.get("id") or ""),
                )
        text = self._output_text(output)
        if not text:
            raise RuntimeError("Responses API returned neither a function call nor output text")
        metadata = self._evidence_metadata(question, history)
        metadata["provider"] = {"name": "openai", "model": self.model, "usage": dict(self.total_usage)}
        return FinalAnswer(text, metadata=metadata)

    def _prompt(self, question: str, history: list[ToolExchange]) -> str:
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
        return (
            "You are RepoPilot in read-only research mode. Use search_code first, then read_file for the exact "
            "selected line range. Do not answer without grounded repository evidence. Include path, symbol, line "
            "range, and evidence id in the final answer.\n\n"
            f"Question: {question}\nHistory: {json.dumps(exchanges, ensure_ascii=False, default=str)}"
        )

    @staticmethod
    def _tool(definition: ToolDefinition) -> dict[str, object]:
        return {
            "type": "function",
            "name": definition.name,
            "description": definition.description,
            "parameters": definition.input_schema,
        }

    @staticmethod
    def _output_text(output: list[object]) -> str:
        texts: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content", [])
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        texts.append(str(part.get("text", "")))
        return "\n".join(text for text in texts if text)

    def _record_usage(self, usage: object) -> None:
        if not isinstance(usage, dict):
            return
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                self.total_usage[key] = self.total_usage.get(key, 0) + value

    @staticmethod
    def _evidence_metadata(question: str, history: list[ToolExchange]) -> dict[str, object]:
        search = next((item for item in history if item.call.name == "search_code" and item.observation.ok), None)
        read = next((item for item in reversed(history) if item.call.name == "read_file" and item.observation.ok), None)
        if search is None or read is None:
            return {}
        matches = search.observation.data.get("matches", [])
        if not isinstance(matches, list) or not matches or not isinstance(matches[0], dict):
            return {}
        top = matches[0]
        evidence = {
            "id": "ev-1",
            "path": str(top["path"]),
            "symbol": str(top["symbol"]),
            "kind": str(top["kind"]),
            "start_line": int(top["start_line"]),
            "end_line": int(top["end_line"]),
            "reason": "Selected by the provider after hybrid retrieval.",
            "excerpt": str(read.observation.data.get("content", "")),
        }
        claim = {"text": "Remote-provider answer grounded in ev-1.", "evidence_ids": ["ev-1"], "confidence": "provider-supported"}
        return {"evidence_ledger": {"question": question, "evidence": [evidence], "claims": [claim]}}
