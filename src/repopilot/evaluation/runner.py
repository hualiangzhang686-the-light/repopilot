from __future__ import annotations

import json
import sys
import tempfile
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from repopilot.agent.loop import AgentLoop
from repopilot.agent.models import CodeResearchModel, ToolCall
from repopilot.agent.stop_conditions import StopController
from repopilot.fix.engine import FixEngine
from repopilot.harness.permissions import Capability, PermissionGate, RepositoryBoundary
from repopilot.harness.process import CommandRunner
from repopilot.retrieval.evidence import CitationValidator, EvidenceLedger
from repopilot.tools.base import ToolContext, ToolDefinition, ToolExchange
from repopilot.tools.code import register_code_tools
from repopilot.tools.filesystem import register_read_tools
from repopilot.tools.registry import ToolRegistry
from repopilot.triage.engine import IssueTriageEngine


@dataclass(frozen=True)
class TaskResult:
    id: str
    type: str
    passed: bool
    expected: dict[str, object]
    actual: dict[str, object]
    duration_seconds: float
    tool_calls: int
    citation_valid: bool | None
    tokens: int | None
    cost_usd: float | None
    failure_layer: str | None


@dataclass(frozen=True)
class EvalSummary:
    generated_at: str
    total: int
    passed: int
    failed: int
    duration_seconds: float
    results: tuple[TaskResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "duration_seconds": self.duration_seconds,
            "results": [asdict(result) for result in self.results],
        }


class _AlwaysFailModel:
    def decide(self, question: str, history: list[ToolExchange]):
        return ToolCall("fail", {"attempt": len(history)})


class EvalRunner:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve(strict=True)
        self.demo_repo = self.project_root / "examples" / "demo_repo"
        self.fix_repo = self.project_root / "examples" / "fix_repo"

    def run(self, tasks_path: Path) -> EvalSummary:
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        started = time.monotonic()
        results = tuple(self._run_task(task) for task in tasks)
        passed = sum(result.passed for result in results)
        return EvalSummary(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            duration_seconds=round(time.monotonic() - started, 6),
            results=results,
        )

    def _run_task(self, task: dict[str, object]) -> TaskResult:
        started = time.monotonic()
        task_type = str(task["type"])
        try:
            actual, tool_calls, citation_valid = getattr(self, f"_run_{task_type}")(task)
            expected = dict(task["expected"])
            passed = all(actual.get(key) == value for key, value in expected.items())
            failure_layer = None if passed else task_type
        except Exception as exc:
            expected = dict(task["expected"])
            actual = {"error": f"{type(exc).__name__}: {exc}"}
            tool_calls = 0
            citation_valid = None
            passed = False
            failure_layer = "harness"
        return TaskResult(
            id=str(task["id"]),
            type=task_type,
            passed=passed,
            expected=expected,
            actual=actual,
            duration_seconds=round(time.monotonic() - started, 6),
            tool_calls=tool_calls,
            citation_valid=citation_valid,
            tokens=None,
            cost_usd=None,
            failure_layer=failure_layer,
        )

    def _run_research(self, task: dict[str, object]):
        boundary = RepositoryBoundary(self.demo_repo)
        registry = ToolRegistry()
        register_read_tools(registry)
        register_code_tools(registry)
        result = AgentLoop(
            model=CodeResearchModel(),
            registry=registry,
            context=ToolContext(boundary.root, boundary),
        ).run(str(task["input"]))
        ledger = EvidenceLedger.from_dict(result.metadata["evidence_ledger"])
        errors = CitationValidator(boundary).validate(ledger)
        evidence = ledger.evidence[0]
        return {"path": evidence.path, "symbol": evidence.symbol, "status": result.status}, result.steps, not errors

    def _run_triage(self, task: dict[str, object]):
        text = (self.project_root / str(task["input"])).read_text(encoding="utf-8")
        result = IssueTriageEngine(self.demo_repo).triage(text)
        return {"status": result.status, "hypotheses": len(result.hypotheses)}, 1 if result.evidence else 0, None

    def _run_fix(self, task: dict[str, object]):
        text = (self.project_root / str(task["input"])).read_text(encoding="utf-8")
        result = FixEngine(self.fix_repo).fix(text)
        calls = int(result.pre_test is not None) + int(result.post_test is not None)
        return {"status": result.status, "review": result.review.decision}, calls, None

    def _run_safety(self, task: dict[str, object]):
        case = str(task["input"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gate = PermissionGate(root, command_allowlist=((str(Path(sys.executable).resolve()), "-c"),))
            if case == "relative_path_escape":
                try:
                    RepositoryBoundary(root).resolve("../../secret.txt")
                    denied = False
                except PermissionError:
                    denied = True
            elif case == "external_capability":
                denied = not gate.check(Capability.EXTERNAL).allowed
            else:
                denied = not gate.check(Capability.EXECUTE, command=("git", "push")).allowed
        return {"denied": denied}, 1, None

    def _run_resilience(self, task: dict[str, object]):
        case = str(task["input"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            python = str(Path(sys.executable).resolve())
            if case == "process_timeout":
                gate = PermissionGate(root, command_allowlist=((python, "-c"),))
                result = CommandRunner(root, gate).run((python, "-c", "import time; time.sleep(1)"), timeout_seconds=0.02)
                stopped = result.timed_out
                calls = 1
            else:
                registry = ToolRegistry()

                def fail(context, arguments):
                    raise RuntimeError("boom")

                registry.register(ToolDefinition("fail", "fail", {"type": "object", "properties": {}}, fail))
                boundary = RepositoryBoundary(root)
                result = AgentLoop(
                    model=_AlwaysFailModel(),
                    registry=registry,
                    context=ToolContext(boundary.root, boundary),
                    stop_controller=StopController(max_steps=5, repeat_limit=5, max_consecutive_failures=2),
                ).run("fail")
                stopped = result.stop_reason == "consecutive_tool_failures"
                calls = result.steps
        return {"stopped": stopped}, calls, None

    def write_outputs(self, summary: EvalSummary, results_path: Path, report_path: Path, baseline_path: Path) -> None:
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        counts = Counter(result.type for result in summary.results)
        passed = Counter(result.type for result in summary.results if result.passed)
        average_calls = sum(result.tool_calls for result in summary.results) / max(1, summary.total)
        lines = [
            "# RepoPilot Evaluation Report",
            "",
            f"Generated: `{summary.generated_at}`",
            "",
            f"Fixed suite result: **{summary.passed}/{summary.total} passed** in {summary.duration_seconds:.3f}s.",
            "",
            "| Category | Passed | Total |",
            "|---|---:|---:|",
        ]
        for category in ("research", "triage", "fix", "safety", "resilience"):
            lines.append(f"| {category} | {passed[category]} | {counts[category]} |")
        lines.extend(
            [
                "",
                f"Average recorded tool/process calls per task: `{average_calls:.2f}`.",
                "",
                "Token and cost values are `null` because this run used deterministic local models and no remote API. This is an explicit measurement boundary, not zero token cost.",
                "",
                "## mini-swe-agent baseline",
                "",
                f"Status: **{baseline['status']}**. Planned controlled tasks: {', '.join(baseline['tasks'])}.",
                "",
                baseline["note"],
                "",
                "The baseline is therefore reproducibly specified but not scored. RepoPilot and mini-swe-agent must use the same remote model and credentials before latency, token, cost, or success comparisons are valid.",
                "",
                "## Artifacts",
                "",
                f"- Machine-readable results: `{results_path.as_posix()}`",
                "- Fixed task definitions: `eval/tasks.json`",
                "- Baseline contract: `eval/mini_swe_baseline.json`",
            ]
        )
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
