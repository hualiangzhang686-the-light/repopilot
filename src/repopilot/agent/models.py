from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias
from uuid import uuid4

from repopilot.tools.base import ToolExchange


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, object]
    call_id: str = ""

    def __post_init__(self) -> None:
        if not self.call_id:
            object.__setattr__(self, "call_id", uuid4().hex)


@dataclass(frozen=True)
class FinalAnswer:
    content: str


ModelDecision: TypeAlias = ToolCall | FinalAnswer


class AgentModel(Protocol):
    def decide(self, question: str, history: list[ToolExchange]) -> ModelDecision:
        """Return either the next tool request or the final answer."""


class ScriptedModel:
    """Deterministic model double for the Day 1 research workflow."""

    def decide(self, question: str, history: list[ToolExchange]) -> ModelDecision:
        if not history:
            return ToolCall("list_files", {"path": "."})

        last = history[-1]
        if last.call.name == "list_files":
            return ToolCall("search_text", {"path": ".", "query": self._search_term(question)})

        if last.call.name == "search_text":
            matches = last.observation.data.get("matches", []) if last.observation.ok else []
            if not isinstance(matches, list) or not matches:
                return FinalAnswer("没有找到与问题匹配的代码文本。")
            first = matches[0]
            if not isinstance(first, dict):
                return FinalAnswer("检索结果格式无效，无法继续读取证据。")
            line = int(first.get("line", 1))
            return ToolCall(
                "read_file",
                {
                    "path": str(first.get("path", "")),
                    "start_line": max(1, line - 3),
                    "end_line": line + 8,
                },
            )

        if last.call.name == "read_file":
            if not last.observation.ok:
                return FinalAnswer(f"文件读取失败：{last.observation.error}")
            data = last.observation.data
            path = data.get("path", "未知文件")
            start = data.get("start_line", "?")
            end = data.get("end_line", "?")
            return FinalAnswer(f"相关逻辑位于 {path}:{start}-{end}。该范围已由 read_file 工具实际读取。")

        return FinalAnswer(f"工具 {last.call.name} 已执行，但 ScriptedModel 没有后续脚本。")

    @staticmethod
    def _search_term(question: str) -> str:
        lowered = question.lower()
        mappings = (
            (("登录", "login", "signin", "sign in"), "login"),
            (("认证", "鉴权", "auth"), "auth"),
            (("超时", "timeout"), "timeout"),
        )
        for variants, term in mappings:
            if any(variant in lowered for variant in variants):
                return term
        ascii_words = [word.strip(".,?!:;()[]{}\"'") for word in lowered.split()]
        candidates = [word for word in ascii_words if len(word) >= 3 and word.isascii()]
        return max(candidates, key=len) if candidates else question.strip()

