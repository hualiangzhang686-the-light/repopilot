from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from repopilot.agent.models import ToolCall
    from repopilot.harness.permissions import RepositoryBoundary


@dataclass(frozen=True)
class Observation:
    ok: bool
    data: dict[str, object] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def success(cls, data: dict[str, object]) -> "Observation":
        return cls(ok=True, data=data)

    @classmethod
    def failure(cls, error: str) -> "Observation":
        return cls(ok=False, error=error)


@dataclass(frozen=True)
class ToolContext:
    repository_root: Path
    boundary: "RepositoryBoundary"


ToolHandler = Callable[[ToolContext, dict[str, object]], dict[str, object]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]
    handler: ToolHandler


@dataclass(frozen=True)
class ToolExchange:
    call: "ToolCall"
    observation: Observation
