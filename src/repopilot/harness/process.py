from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from repopilot.harness.permissions import Capability, PermissionGate


@dataclass(frozen=True)
class ExecutionResult:
    command: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float


class CommandRunner:
    """Run one allowlisted process without a shell and enforce a wall-clock timeout."""

    def __init__(self, sandbox_root: Path, gate: PermissionGate) -> None:
        self.sandbox_root = sandbox_root.resolve(strict=True)
        self.gate = gate

    def run(self, command: tuple[str, ...], *, timeout_seconds: float = 60.0) -> ExecutionResult:
        decision = self.gate.check(Capability.EXECUTE, command=command)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=self.sandbox_root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
            )
            return ExecutionResult(
                command=command,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                duration_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                command=command,
                exit_code=None,
                stdout=self._text(exc.stdout),
                stderr=self._text(exc.stderr),
                timed_out=True,
                duration_seconds=time.monotonic() - started,
            )

    @staticmethod
    def _text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        return value.decode(errors="replace") if isinstance(value, bytes) else value
