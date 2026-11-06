from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from enum import StrEnum


class RepositoryBoundary:
    """Resolve paths while preventing absolute and symlink escapes."""

    def __init__(self, repository_root: Path) -> None:
        root = repository_root.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(str(repository_root))
        self.root = root

    def resolve(self, requested: str, *, must_exist: bool = False) -> Path:
        raw = Path(requested).expanduser()
        candidate = raw.resolve(strict=False) if raw.is_absolute() else (self.root / raw).resolve(strict=False)
        if not candidate.is_relative_to(self.root):
            raise PermissionError(f"path escapes repository root: {requested}")
        if must_exist and not candidate.exists():
            raise FileNotFoundError(requested)
        return candidate


class Capability(StrEnum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    EXTERNAL = "external"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str


class PermissionGate:
    """Central policy for repository capabilities used by the Day 4+ harness."""

    def __init__(self, sandbox_root: Path, *, command_allowlist: tuple[tuple[str, ...], ...] = ()) -> None:
        self.sandbox_root = sandbox_root.resolve(strict=True)
        self.command_allowlist = command_allowlist

    def check(
        self,
        capability: Capability,
        *,
        path: Path | None = None,
        command: tuple[str, ...] | None = None,
    ) -> PermissionDecision:
        if capability is Capability.READ:
            return PermissionDecision(True, "read capability is allowed inside the repository boundary")
        if capability is Capability.WRITE:
            if path is None:
                return PermissionDecision(False, "write requires an explicit target path")
            resolved = path.resolve(strict=False)
            allowed = resolved.is_relative_to(self.sandbox_root)
            return PermissionDecision(allowed, "target is inside sandbox" if allowed else "write target escapes sandbox")
        if capability is Capability.EXECUTE:
            if not command:
                return PermissionDecision(False, "execute requires a command")
            allowed = any(command[: len(prefix)] == prefix for prefix in self.command_allowlist)
            return PermissionDecision(allowed, "command matches allowlist" if allowed else "command is not allowlisted")
        if capability is Capability.DELETE:
            return PermissionDecision(False, "delete capability is disabled")
        return PermissionDecision(False, "external capability is disabled")
