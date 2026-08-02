from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable

from repopilot.agent.models import ToolCall


class StopController:
    def __init__(
        self,
        *,
        max_steps: int = 8,
        timeout_seconds: float = 30.0,
        repeat_limit: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if repeat_limit < 1:
            raise ValueError("repeat_limit must be at least 1")
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.repeat_limit = repeat_limit
        self.clock = clock
        self._started_at = 0.0
        self._calls: Counter[str] = Counter()

    def start(self) -> None:
        self._started_at = self.clock()
        self._calls.clear()

    def before_model_call(self, completed_steps: int) -> str | None:
        if completed_steps >= self.max_steps:
            return "max_steps"
        if self.clock() - self._started_at >= self.timeout_seconds:
            return "timeout"
        return None

    def register_tool_call(self, call: ToolCall) -> str | None:
        signature = json.dumps(
            {"name": call.name, "arguments": call.arguments},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        self._calls[signature] += 1
        if self._calls[signature] > self.repeat_limit:
            return "repeated_tool_call"
        return None
