from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

from repopilot.fix.models import FixResult, PatchSpec, ReviewResult
from repopilot.harness.permissions import Capability, PermissionGate, RepositoryBoundary
from repopilot.harness.process import CommandRunner, ExecutionResult
from repopilot.harness.sandbox import SandboxWorkspace
from repopilot.harness.trace import TraceWriter
from repopilot.triage.engine import IssueTriageEngine


FIX_BLOCK = re.compile(r"```repopilot-fix\s*(\{.*?\})\s*```", re.DOTALL)


class IssueFixParser:
    def parse(self, issue_text: str) -> PatchSpec:
        match = FIX_BLOCK.search(issue_text)
        if not match:
            raise ValueError("issue has no repopilot-fix block")
        value = json.loads(match.group(1))
        test = value.get("test", [])
        if not isinstance(test, list) or not test:
            raise ValueError("fix block requires a non-empty test command")
        return PatchSpec(
            path=str(value["path"]),
            old=str(value["old"]),
            new=str(value["new"]),
            test=tuple(str(part) for part in test),
        )


class FixEngine:
    def __init__(self, repository_root: Path) -> None:
        self.source_boundary = RepositoryBoundary(repository_root)

    def fix(self, issue_text: str, *, trace: TraceWriter | None = None) -> FixResult:
        writer = trace or TraceWriter.disabled()
        goal = IssueTriageEngine._goal(issue_text)
        writer.emit("fix.start", step=0, data={"goal": goal})
        try:
            spec = IssueFixParser().parse(issue_text)
            self.source_boundary.resolve(spec.path, must_exist=True)
        except (ValueError, PermissionError, FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
            writer.emit("fix.stop", step=0, data={"reason": "invalid_or_forbidden_patch", "error": str(exc)})
            return self._rejected(goal, f"{type(exc).__name__}: {exc}", writer.path_string)

        triage = IssueTriageEngine(self.source_boundary.root).triage(issue_text)
        evidence = tuple(item.id for item in triage.evidence if item.path == spec.path)
        if triage.status != "ready" or not evidence:
            writer.emit("fix.stop", step=1, data={"reason": "insufficient_evidence"})
            return self._rejected(goal, "patch path is not supported by triage evidence", writer.path_string)

        try:
            command = self._command(spec.test)
        except PermissionError as exc:
            writer.emit("fix.stop", step=1, data={"reason": "command_not_allowlisted", "error": str(exc)})
            return self._rejected(goal, str(exc), writer.path_string)

        with SandboxWorkspace(self.source_boundary.root) as sandbox:
            allowlist = ((command[0], "-c"), (command[0], "-m", "unittest"))
            gate = PermissionGate(sandbox, command_allowlist=allowlist)
            runner = CommandRunner(sandbox, gate)
            pre = runner.run(command, timeout_seconds=10.0)
            writer.emit("fix.pre_test", step=2, data=self._execution(pre))

            target = (sandbox / spec.path).resolve(strict=True)
            write_decision = gate.check(Capability.WRITE, path=target)
            if not write_decision.allowed:
                writer.emit("fix.stop", step=2, data={"reason": write_decision.reason})
                return self._rejected(goal, write_decision.reason, writer.path_string)
            original = target.read_text(encoding="utf-8")
            if original.count(spec.old) != 1:
                writer.emit("fix.stop", step=2, data={"reason": "patch_anchor_mismatch"})
                return self._rejected(goal, "patch anchor must occur exactly once", writer.path_string)
            updated = original.replace(spec.old, spec.new, 1)
            target.write_text(updated, encoding="utf-8")
            diff = "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    updated.splitlines(keepends=True),
                    fromfile=f"a/{spec.path}",
                    tofile=f"b/{spec.path}",
                )
            )
            writer.emit("fix.patch", step=3, data={"path": spec.path, "diff_lines": len(diff.splitlines())})

            post = runner.run(command, timeout_seconds=10.0)
            writer.emit("fix.post_test", step=4, data=self._execution(post))
            review = self._review(diff, post)
            status = "completed" if review.decision == "PASS" else "failed"
            stop_reason = "verified_patch" if status == "completed" else "review_revision_limit"
            writer.emit("fix.review", step=5, data={"decision": review.decision, "reasons": review.reasons})
            writer.emit("fix.stop", step=5, data={"reason": stop_reason})
            return FixResult(
                status=status,
                goal=goal,
                patch_path=spec.path,
                evidence_ids=evidence,
                pre_test=self._execution(pre),
                post_test=self._execution(post),
                diff=diff,
                review=review,
                sandbox_isolated=True,
                stop_reason=stop_reason,
                trace_path=writer.path_string,
            )

    @staticmethod
    def _command(parts: tuple[str, ...]) -> tuple[str, ...]:
        python = str(Path(sys.executable).resolve())
        command = tuple(python if part == "{python}" else part for part in parts)
        allowed = (
            len(command) >= 3 and command[0] == python and command[1] == "-c"
        ) or (
            len(command) >= 4 and command[:3] == (python, "-m", "unittest")
        )
        if not allowed:
            raise PermissionError("test command must use {python} -c or {python} -m unittest")
        return command

    @staticmethod
    def _execution(result: ExecutionResult) -> dict[str, object]:
        return {
            "command": result.command,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "duration_seconds": round(result.duration_seconds, 6),
        }

    @staticmethod
    def _review(diff: str, post: ExecutionResult) -> ReviewResult:
        reasons: list[str] = []
        if not diff:
            reasons.append("patch produced no diff")
        if post.timed_out:
            reasons.append("post-patch test timed out")
        elif post.exit_code != 0:
            reasons.append(f"post-patch test exited with {post.exit_code}")
        if reasons:
            return ReviewResult("REVISE_ONCE", tuple(reasons), 1)
        return ReviewResult("PASS", ("diff is non-empty and focused test passed",), 0)

    @staticmethod
    def _rejected(goal: str, reason: str, trace_path: str | None) -> FixResult:
        return FixResult(
            status="rejected",
            goal=goal,
            patch_path=None,
            evidence_ids=(),
            pre_test=None,
            post_test=None,
            diff="",
            review=ReviewResult("REJECT", (reason,), 0),
            sandbox_isolated=True,
            stop_reason=reason,
            trace_path=trace_path,
        )
