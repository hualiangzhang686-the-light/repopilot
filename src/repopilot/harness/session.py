from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4


@dataclass
class SessionState:
    session_id: str
    goal: str
    status: str = "running"
    evidence: list[dict[str, object]] = field(default_factory=list)
    plan: list[dict[str, object]] = field(default_factory=list)
    key_state: dict[str, object] = field(default_factory=dict)
    history_summary: str = ""


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, state: SessionState) -> Path:
        path = self.root / f"{state.session_id}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return path

    def load(self, session_id: str) -> SessionState:
        value = json.loads((self.root / f"{session_id}.json").read_text(encoding="utf-8"))
        return SessionState(**value)


class ContextCompactor:
    def compact(self, state: SessionState, events: list[str], *, keep_recent: int = 5) -> SessionState:
        omitted = max(0, len(events) - keep_recent)
        recent = events[-keep_recent:]
        state.history_summary = f"omitted_events={omitted}; recent=" + " | ".join(recent)
        return state


@dataclass(frozen=True)
class CapturedOutput:
    inline: str
    artifact_path: str | None
    sha256: str
    truncated: bool


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)

    def capture(self, content: str, *, max_inline_chars: int = 2000) -> CapturedOutput:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if len(content) <= max_inline_chars:
            return CapturedOutput(content, None, digest, False)
        path = self.root / f"artifact-{uuid4().hex}.txt"
        path.write_text(content, encoding="utf-8")
        inline = content[:max_inline_chars] + f"\n...[truncated; artifact={path.name}; sha256={digest}]"
        return CapturedOutput(inline, path.name, digest, True)
