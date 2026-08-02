from __future__ import annotations

from dataclasses import dataclass

from repopilot.agent.models import AgentModel, FinalAnswer, ToolCall
from repopilot.agent.stop_conditions import StopController
from repopilot.harness.trace import TraceWriter
from repopilot.tools.base import ToolContext, ToolExchange
from repopilot.tools.registry import ToolRegistry


@dataclass(frozen=True)
class RunResult:
    status: str
    answer: str | None
    stop_reason: str
    steps: int
    history: tuple[ToolExchange, ...]
    trace_path: str | None


class AgentLoop:
    def __init__(
        self,
        *,
        model: AgentModel,
        registry: ToolRegistry,
        context: ToolContext,
        stop_controller: StopController | None = None,
        trace: TraceWriter | None = None,
    ) -> None:
        self.model = model
        self.registry = registry
        self.context = context
        self.stop_controller = stop_controller or StopController()
        self.trace = trace or TraceWriter.disabled()

    def run(self, question: str) -> RunResult:
        history: list[ToolExchange] = []
        steps = 0
        self.stop_controller.start()
        self.trace.emit("run.start", step=steps, data={"question": question})

        while True:
            reason = self.stop_controller.before_model_call(steps)
            if reason:
                return self._stopped(reason, steps, history)

            self.trace.emit("model.request", step=steps, data={"history_size": len(history)})
            try:
                decision = self.model.decide(question, history)
            except Exception as exc:  # Model adapters are an external boundary.
                self.trace.emit(
                    "model.error",
                    step=steps,
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
                return self._stopped("model_error", steps, history)

            if isinstance(decision, FinalAnswer):
                self.trace.emit("model.final", step=steps, data={"answer": decision.content})
                self.trace.emit("loop.stop", step=steps, data={"reason": "final_answer"})
                return RunResult(
                    status="completed",
                    answer=decision.content,
                    stop_reason="final_answer",
                    steps=steps,
                    history=tuple(history),
                    trace_path=self.trace.path_string,
                )

            if not isinstance(decision, ToolCall):
                self.trace.emit("model.error", step=steps, data={"error": "invalid model decision"})
                return self._stopped("invalid_model_decision", steps, history)

            self.trace.emit(
                "tool.request",
                step=steps + 1,
                data={"call_id": decision.call_id, "name": decision.name, "arguments": decision.arguments},
            )
            duplicate_reason = self.stop_controller.register_tool_call(decision)
            if duplicate_reason:
                return self._stopped(duplicate_reason, steps, history)

            observation = self.registry.execute(decision, self.context)
            steps += 1
            history.append(ToolExchange(decision, observation))
            self.trace.emit(
                "tool.result",
                step=steps,
                data={
                    "call_id": decision.call_id,
                    "name": decision.name,
                    "ok": observation.ok,
                    "data": observation.data,
                    "error": observation.error,
                },
            )

    def _stopped(self, reason: str, steps: int, history: list[ToolExchange]) -> RunResult:
        self.trace.emit("loop.stop", step=steps, data={"reason": reason})
        return RunResult(
            status="stopped",
            answer=None,
            stop_reason=reason,
            steps=steps,
            history=tuple(history),
            trace_path=self.trace.path_string,
        )

