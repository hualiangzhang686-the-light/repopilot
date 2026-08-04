from __future__ import annotations

import json
from pathlib import Path


class TraceReplay:
    def __init__(self, path: Path) -> None:
        self.path = path

    def records(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}") from exc
            if not isinstance(value, dict) or not isinstance(value.get("event"), str):
                raise ValueError(f"invalid trace record at line {line_number}")
            records.append(value)
        run_ids = {record.get("run_id") for record in records}
        if len(run_ids) > 1:
            raise ValueError("trace contains multiple run ids")
        return records

    def timeline(self) -> list[str]:
        return [
            f"step={record.get('step', '?')} event={record['event']} data={json.dumps(record.get('data', {}), ensure_ascii=False, sort_keys=True)}"
            for record in self.records()
        ]
