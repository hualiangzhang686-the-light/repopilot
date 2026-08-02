from __future__ import annotations

from repopilot.agent.models import ToolCall
from repopilot.tools.base import Observation, ToolContext, ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool already registered: {definition.name}")
        self._tools[definition.name] = definition

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())

    def execute(self, call: ToolCall, context: ToolContext) -> Observation:
        definition = self._tools.get(call.name)
        if definition is None:
            return Observation.failure(f"unknown tool: {call.name}")

        required = definition.input_schema.get("required", [])
        missing = [name for name in required if name not in call.arguments]
        if missing:
            return Observation.failure(f"missing required arguments: {', '.join(missing)}")

        try:
            result = definition.handler(context, call.arguments)
            if not isinstance(result, dict):
                return Observation.failure(f"tool {call.name} returned a non-object result")
            return Observation.success(result)
        except Exception as exc:
            return Observation.failure(f"{type(exc).__name__}: {exc}")

