from __future__ import annotations

from pathlib import Path


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

