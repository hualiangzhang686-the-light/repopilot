from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class TraceWriter:
    def __init__(self, path: Path | None, *, run_id: str | None = None, reset: bool = True) -> None:
        self.path = path
        self.run_id = run_id or uuid4().hex
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if reset:
                self.path.write_text("", encoding="utf-8")

    @classmethod
    def disabled(cls) -> "TraceWriter":
        return cls(None)

    @property
    def path_string(self) -> str | None:
        return str(self.path) if self.path is not None else None

    def emit(self, event: str, *, step: int, data: dict[str, object]) -> None:
        if self.path is None:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event": event,
            "step": step,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")
