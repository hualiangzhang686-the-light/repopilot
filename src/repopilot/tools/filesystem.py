from __future__ import annotations

from pathlib import Path

from repopilot.tools.base import ToolContext, ToolDefinition
from repopilot.tools.registry import ToolRegistry


def _relative(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    return relative.as_posix() or "."


def list_files(context: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    path = context.boundary.resolve(str(arguments.get("path", ".")), must_exist=True)
    if not path.is_dir():
        raise NotADirectoryError(str(arguments.get("path", ".")))
    max_results = int(arguments.get("max_results", 200))
    if max_results < 1:
        raise ValueError("max_results must be positive")

    files: list[str] = []
    for candidate in sorted(path.rglob("*")):
        if candidate.is_file() and ".git" not in candidate.parts:
            files.append(_relative(context.repository_root, candidate))
            if len(files) >= max_results:
                break
    return {"path": _relative(context.repository_root, path), "files": files, "truncated": len(files) >= max_results}


def read_file(context: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    requested = str(arguments["path"])
    path = context.boundary.resolve(requested, must_exist=True)
    if not path.is_file():
        raise FileNotFoundError(requested)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return {
            "path": _relative(context.repository_root, path),
            "start_line": 0,
            "end_line": 0,
            "content": "",
        }
    start = int(arguments.get("start_line", 1))
    end = int(arguments.get("end_line", len(lines)))
    if start < 1 or end < start:
        raise ValueError("line range must satisfy 1 <= start_line <= end_line")
    if start > len(lines):
        raise ValueError(f"start_line {start} exceeds file length {len(lines)}")
    end = min(end, len(lines))
    selected = lines[start - 1 : end]
    return {
        "path": _relative(context.repository_root, path),
        "start_line": start,
        "end_line": end,
        "content": "\n".join(selected),
    }


def search_text(context: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    query = str(arguments["query"])
    if not query:
        raise ValueError("query must not be empty")
    path = context.boundary.resolve(str(arguments.get("path", ".")), must_exist=True)
    max_results = int(arguments.get("max_results", 50))
    if max_results < 1:
        raise ValueError("max_results must be positive")

    candidates = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    matches: list[dict[str, object]] = []
    needle = query.casefold()
    for candidate in candidates:
        if ".git" in candidate.parts:
            continue
        try:
            content = candidate.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if needle in line.casefold():
                matches.append(
                    {"path": _relative(context.repository_root, candidate), "line": line_number, "text": line.strip()}
                )
                if len(matches) >= max_results:
                    return {"query": query, "matches": matches, "truncated": True}
    return {"query": query, "matches": matches, "truncated": False}


def register_read_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="list_files",
            description="List files below a repository-relative directory.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}, "max_results": {"type": "integer"}},
                "required": [],
            },
            handler=list_files,
        )
    )
    registry.register(
        ToolDefinition(
            name="read_file",
            description="Read an inclusive line range from a UTF-8 text file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
            handler=read_file,
        )
    )
    registry.register(
        ToolDefinition(
            name="search_text",
            description="Search UTF-8 repository text and return file paths and line numbers.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
            handler=search_text,
        )
    )
