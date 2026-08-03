from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.harness.permissions import RepositoryBoundary
from repopilot.harness.trace import TraceWriter
from repopilot.retrieval.evidence import CitationValidator, EvidenceLedger


def main() -> int:
    trace = TraceWriter(PROJECT_ROOT / "traces" / "day2-invalid-citation.jsonl")
    ledger = EvidenceLedger.from_dict(
        {
            "question": "Where is the missing function?",
            "evidence": [
                {
                    "id": "ev-404",
                    "path": "app/missing.py",
                    "symbol": "missing",
                    "kind": "function",
                    "start_line": 1,
                    "end_line": 2,
                    "reason": "Deliberately fabricated failure fixture.",
                    "excerpt": "def missing():\n    pass",
                }
            ],
            "claims": [{"text": "The function exists.", "evidence_ids": ["ev-404"], "confidence": "unsupported"}],
        }
    )
    trace.emit("validation.start", step=0, data={"evidence_ids": ["ev-404"]})
    errors = CitationValidator(RepositoryBoundary(PROJECT_ROOT / "examples" / "demo_repo")).validate(ledger)
    trace.emit("validation.result", step=1, data={"ok": not errors, "errors": errors})
    trace.emit("validation.stop", step=1, data={"reason": "invalid_citation" if errors else "valid"})
    print("\n".join(errors))
    return 0 if errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
