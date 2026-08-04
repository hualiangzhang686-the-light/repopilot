from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.harness.permissions import Capability, PermissionGate
from repopilot.harness.session import ContextCompactor, SessionState, SessionStore
from repopilot.harness.trace import TraceWriter


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        success = TraceWriter(PROJECT_ROOT / "traces" / "day4-session-success.jsonl")
        state = SessionState("demo-session", "preserve evidence across recovery", evidence=[{"id": "ev-1"}])
        SessionStore(root / "sessions").save(state)
        resumed = SessionStore(root / "sessions").load(state.session_id)
        ContextCompactor().compact(resumed, [f"event-{index}" for index in range(8)], keep_recent=2)
        success.emit("session.resumed", step=1, data={"goal": resumed.goal, "evidence": resumed.evidence})
        success.emit("context.compacted", step=2, data={"summary": resumed.history_summary})

        failure = TraceWriter(PROJECT_ROOT / "traces" / "day4-permission-denied.jsonl")
        gate = PermissionGate(root)
        for step, capability in enumerate((Capability.DELETE, Capability.EXTERNAL), start=1):
            decision = gate.check(capability)
            failure.emit(
                "permission.denied",
                step=step,
                data={"capability": capability.value, "allowed": decision.allowed, "reason": decision.reason},
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
