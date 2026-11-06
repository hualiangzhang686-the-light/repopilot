from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.agent.loop import AgentLoop
from repopilot.agent.models import ToolCall
from repopilot.agent.stop_conditions import StopController
from repopilot.harness.permissions import Capability, PermissionGate, RepositoryBoundary
from repopilot.harness.process import CommandRunner
from repopilot.harness.session import ArtifactStore, ContextCompactor, SessionState, SessionStore
from repopilot.tools.base import ToolContext, ToolDefinition, ToolExchange
from repopilot.tools.registry import ToolRegistry


class FailingModel:
    def decide(self, question: str, history: list[ToolExchange]):
        return ToolCall("fail", {"attempt": len(history)})


class Day4HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_relative_path_escape_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            RepositoryBoundary(self.root).resolve("../../secret.txt")

    def test_absolute_path_escape_is_rejected(self) -> None:
        outside = self.root.parent / "secret.txt"
        with self.assertRaises(PermissionError):
            RepositoryBoundary(self.root).resolve(str(outside))

    def test_read_capability_is_allowed(self) -> None:
        gate = PermissionGate(self.root)
        self.assertTrue(gate.check(Capability.READ).allowed)

    def test_write_is_only_allowed_inside_sandbox(self) -> None:
        gate = PermissionGate(self.root)
        self.assertTrue(gate.check(Capability.WRITE, path=self.root / "file.py").allowed)
        self.assertFalse(gate.check(Capability.WRITE, path=self.root.parent / "file.py").allowed)

    def test_delete_and_external_capabilities_are_denied(self) -> None:
        gate = PermissionGate(self.root)
        self.assertFalse(gate.check(Capability.DELETE).allowed)
        self.assertFalse(gate.check(Capability.EXTERNAL).allowed)

    def test_command_allowlist_accepts_only_matching_prefix(self) -> None:
        executable = str(Path(sys.executable).resolve())
        gate = PermissionGate(self.root, command_allowlist=((executable, "-c"),))
        self.assertTrue(gate.check(Capability.EXECUTE, command=(executable, "-c", "print('ok')")).allowed)
        self.assertFalse(gate.check(Capability.EXECUTE, command=("git", "push")).allowed)

    def test_command_runner_enforces_process_timeout(self) -> None:
        executable = str(Path(sys.executable).resolve())
        gate = PermissionGate(self.root, command_allowlist=((executable, "-c"),))
        result = CommandRunner(self.root, gate).run(
            (executable, "-c", "import time; time.sleep(1)"), timeout_seconds=0.02
        )
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)

    def test_session_can_be_saved_and_resumed(self) -> None:
        store = SessionStore(self.root / "sessions")
        state = SessionState("session-1", "fix login", evidence=[{"id": "ev-1"}], key_state={"step": 2})
        store.save(state)
        self.assertEqual(store.load("session-1"), state)

    def test_compaction_preserves_goal_evidence_plan_and_key_state(self) -> None:
        state = SessionState(
            "session-2",
            "fix login",
            evidence=[{"id": "ev-1"}],
            plan=[{"step": 1}],
            key_state={"status": "triaged"},
        )
        compacted = ContextCompactor().compact(state, [f"event-{index}" for index in range(10)], keep_recent=2)
        self.assertEqual(compacted.goal, "fix login")
        self.assertEqual(compacted.evidence, [{"id": "ev-1"}])
        self.assertEqual(compacted.plan, [{"step": 1}])
        self.assertEqual(compacted.key_state, {"status": "triaged"})
        self.assertIn("omitted_events=8", compacted.history_summary)

    def test_large_output_is_truncated_and_saved_as_artifact(self) -> None:
        store = ArtifactStore(self.root / "artifacts")
        captured = store.capture("x" * 100, max_inline_chars=10)
        self.assertTrue(captured.truncated)
        self.assertEqual((store.root / str(captured.artifact_path)).read_text(encoding="utf-8"), "x" * 100)

    def test_consecutive_tool_failures_stop_loop(self) -> None:
        registry = ToolRegistry()

        def fail(context, arguments):
            raise RuntimeError("boom")

        registry.register(ToolDefinition("fail", "fail", {"type": "object", "properties": {}}, fail))
        boundary = RepositoryBoundary(self.root)
        result = AgentLoop(
            model=FailingModel(),
            registry=registry,
            context=ToolContext(boundary.root, boundary),
            stop_controller=StopController(max_steps=10, repeat_limit=10, max_consecutive_failures=2),
        ).run("fail")
        self.assertEqual(result.stop_reason, "consecutive_tool_failures")
        self.assertEqual(result.steps, 2)


if __name__ == "__main__":
    unittest.main()
