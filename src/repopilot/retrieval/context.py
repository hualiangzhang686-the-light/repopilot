from __future__ import annotations

import ast
import hashlib
import json
import os
import textwrap
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from repopilot.retrieval.code_index import CodeChunk, HybridRetriever, PythonAstChunker


CACHE_VERSION = 1


def default_symbol_cache_root() -> Path | None:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "repopilot" / "symbol-cards"
    try:
        return Path.home() / ".cache" / "repopilot" / "symbol-cards"
    except RuntimeError:
        return None


@dataclass(frozen=True)
class SymbolCard:
    path: str
    symbol: str
    kind: str
    signature: str
    summary: str
    start_line: int
    end_line: int
    revision: str
    observed_calls: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    called_by: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.path}::{self.symbol}"

    def retrieval_text(self) -> str:
        return " ".join((self.signature, self.summary, *self.observed_calls, *self.calls, *self.called_by))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "SymbolCard":
        return cls(
            path=str(value["path"]),
            symbol=str(value["symbol"]),
            kind=str(value["kind"]),
            signature=str(value["signature"]),
            summary=str(value["summary"]),
            start_line=int(value["start_line"]),
            end_line=int(value["end_line"]),
            revision=str(value["revision"]),
            observed_calls=tuple(str(item) for item in value.get("observed_calls", [])),
            calls=tuple(str(item) for item in value.get("calls", [])),
            called_by=tuple(str(item) for item in value.get("called_by", [])),
        )

    def as_match(self, score: float) -> dict[str, object]:
        return {
            "path": self.path,
            "symbol": self.symbol,
            "kind": self.kind,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": round(score, 6),
            "signature": self.signature,
            "summary": self.summary,
            "calls": list(self.calls),
            "called_by": list(self.called_by),
            "revision": self.revision,
        }


@dataclass(frozen=True)
class SymbolIndexSnapshot:
    cards: tuple[SymbolCard, ...]
    rebuilt_files: tuple[str, ...]
    reused_files: tuple[str, ...]


@dataclass(frozen=True)
class SymbolMatch:
    card: SymbolCard
    score: float


@dataclass(frozen=True)
class SymbolSearchResult:
    matches: tuple[SymbolMatch, ...]
    snapshot: SymbolIndexSnapshot


@dataclass(frozen=True)
class ContextSource:
    key: str
    role: str
    path: str
    start_line: int
    end_line: int
    content: str


@dataclass(frozen=True)
class ContextBundle:
    query: str
    target: SymbolCard | None
    cards: tuple[SymbolCard, ...]
    sources: tuple[ContextSource, ...]
    estimated_tokens: int
    token_budget: int
    rebuilt_files: tuple[str, ...]
    reused_files: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "target": self.target.to_dict() if self.target else None,
            "cards": [card.to_dict() for card in self.cards],
            "sources": [asdict(source) for source in self.sources],
            "estimated_tokens": self.estimated_tokens,
            "token_budget": self.token_budget,
            "token_estimator": "ceil(chars/4)",
            "cache": {
                "rebuilt_files": list(self.rebuilt_files),
                "reused_files": list(self.reused_files),
            },
        }


class SymbolCardIndex:
    """Persist deterministic symbol cards and rebuild only changed Python files."""

    def __init__(self, repository_root: Path, cache_root: Path | None = None) -> None:
        self.root = repository_root.resolve(strict=True)
        self.cache_root = cache_root.resolve(strict=False) if cache_root else None
        key = hashlib.sha256(str(self.root).casefold().encode("utf-8")).hexdigest()[:20]
        self.cache_path = self.cache_root / f"{key}.json" if self.cache_root else None

    def build(self) -> SymbolIndexSnapshot:
        chunker = PythonAstChunker(self.root)
        cached_files = self._load().get("files", {})
        current: dict[str, dict[str, object]] = {}
        cards: list[SymbolCard] = []
        rebuilt: list[str] = []
        reused: list[str] = []

        for path in chunker.python_files():
            relative = path.relative_to(self.root).as_posix()
            revision = hashlib.sha256(path.read_bytes()).hexdigest()
            cached = cached_files.get(relative) if isinstance(cached_files, dict) else None
            if isinstance(cached, dict) and cached.get("revision") == revision:
                file_cards = [
                    SymbolCard.from_dict(value)
                    for value in cached.get("cards", [])
                    if isinstance(value, dict)
                ]
                reused.append(relative)
            else:
                file_cards = [self._card(chunk, revision) for chunk in chunker.build_file(path)]
                rebuilt.append(relative)
            cards.extend(file_cards)
            current[relative] = {"revision": revision, "cards": []}

        resolved = self._resolve_relationships(cards)
        for card in resolved:
            current[card.path]["cards"].append(card.to_dict())
        self._save({"version": CACHE_VERSION, "files": current})
        return SymbolIndexSnapshot(
            cards=tuple(resolved),
            rebuilt_files=tuple(rebuilt),
            reused_files=tuple(reused),
        )

    def _load(self) -> dict[str, object]:
        if self.cache_path is None or not self.cache_path.exists():
            return {}
        try:
            value = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) and value.get("version") == CACHE_VERSION else {}

    def _save(self, value: dict[str, object]) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.cache_path)

    @staticmethod
    def _card(chunk: CodeChunk, revision: str) -> SymbolCard:
        try:
            tree = ast.parse(textwrap.dedent(chunk.content))
        except SyntaxError:
            tree = ast.Module(body=[], type_ignores=[])
        node = tree if chunk.kind == "module" else next(iter(tree.body), tree)
        signature = SymbolCardIndex._signature(node, chunk)
        summary = ast.get_docstring(node, clean=True) if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else None
        observed_calls = ()
        if chunk.kind in {"function", "method"}:
            observed_calls = tuple(
                sorted(
                    {
                        name
                        for call in ast.walk(node)
                        if isinstance(call, ast.Call) and (name := SymbolCardIndex._call_name(call.func))
                    }
                )
            )
        return SymbolCard(
            path=chunk.path,
            symbol=chunk.symbol,
            kind=chunk.kind,
            signature=signature,
            summary=(summary.strip().splitlines()[0] if summary else signature),
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            revision=revision,
            observed_calls=observed_calls,
        )

    @staticmethod
    def _signature(node: ast.AST, chunk: CodeChunk) -> str:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            return f"{prefix} {node.name}({ast.unparse(node.args)}){returns}"
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(base) for base in node.bases)
            return f"class {node.name}({bases})" if bases else f"class {node.name}"
        return f"module {chunk.symbol}"

    @staticmethod
    def _call_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = SymbolCardIndex._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return None

    @staticmethod
    def _resolve_relationships(cards: list[SymbolCard]) -> list[SymbolCard]:
        by_symbol: dict[str, list[SymbolCard]] = {}
        by_leaf: dict[str, list[SymbolCard]] = {}
        for card in cards:
            by_symbol.setdefault(card.symbol, []).append(card)
            by_leaf.setdefault(card.symbol.rsplit(".", 1)[-1], []).append(card)

        calls_by_key: dict[str, set[str]] = {card.key: set() for card in cards}
        called_by: dict[str, set[str]] = {card.key: set() for card in cards}
        for card in cards:
            for observed in card.observed_calls:
                suffix_matches = [candidate for candidate in cards if candidate.symbol.endswith(f".{observed}")]
                candidates = by_symbol.get(observed, []) or suffix_matches or by_leaf.get(observed.rsplit(".", 1)[-1], [])
                unique = {candidate.key: candidate for candidate in candidates}
                if len(unique) == 1:
                    target = next(iter(unique))
                    calls_by_key[card.key].add(target)
                    called_by[target].add(card.key)

        return sorted(
            (
                replace(
                    card,
                    calls=tuple(sorted(calls_by_key[card.key])),
                    called_by=tuple(sorted(called_by[card.key])),
                )
                for card in cards
            ),
            key=lambda card: (card.path, card.start_line, card.symbol),
        )


class ContextManager:
    """Retrieve symbol cards, expand one hop, then load current source under a budget."""

    def __init__(self, repository_root: Path, cache_root: Path | None = None) -> None:
        self.root = repository_root.resolve(strict=True)
        self.index = SymbolCardIndex(self.root, cache_root)

    def search(self, query: str, *, max_results: int = 5) -> SymbolSearchResult:
        snapshot = self.index.build()
        chunks = [
            CodeChunk(
                card.path,
                card.symbol,
                card.kind,
                card.start_line,
                card.end_line,
                card.retrieval_text(),
            )
            for card in snapshot.cards
        ]
        card_by_location = {
            (card.path, card.symbol, card.start_line, card.end_line): card for card in snapshot.cards
        }
        matches = tuple(
            SymbolMatch(card_by_location[(chunk.path, chunk.symbol, chunk.start_line, chunk.end_line)], score)
            for chunk, score in HybridRetriever(chunks).search(query, max_results=max_results)
        )
        return SymbolSearchResult(matches, snapshot)

    def assemble(self, query: str, *, token_budget: int = 2000, max_cards: int = 8) -> ContextBundle:
        if token_budget < 1:
            raise ValueError("token_budget must be positive")
        result = self.search(query, max_results=max_cards)
        if not result.matches:
            return ContextBundle(query, None, (), (), 0, token_budget, result.snapshot.rebuilt_files, result.snapshot.reused_files)

        target = result.matches[0].card
        by_key = {card.key: card for card in result.snapshot.cards}
        tests = [
            card
            for card in result.snapshot.cards
            if self._is_test(card.path) and target.key in card.calls
        ]
        related_keys = (*target.calls, *target.called_by)
        ordered = [target, *tests, *(by_key[key] for key in related_keys if key in by_key), *(match.card for match in result.matches[1:])]
        unique: list[SymbolCard] = []
        seen: set[str] = set()
        for card in ordered:
            if card.key not in seen:
                unique.append(card)
                seen.add(card.key)

        target_source = self._source(target, "target")
        target_cost = self._tokens(json.dumps(target.to_dict(), ensure_ascii=False)) + self._tokens(target_source.content)
        if target_cost > token_budget:
            raise ValueError(f"token_budget={token_budget} cannot hold the complete target symbol ({target_cost} estimated tokens)")

        selected_cards = [target]
        sources = [target_source]
        used = target_cost
        for card in unique[1:max_cards]:
            card_cost = self._tokens(json.dumps(card.to_dict(), ensure_ascii=False))
            if used + card_cost > token_budget:
                continue
            selected_cards.append(card)
            used += card_cost
            if card.key in target.calls or card.key in target.called_by or self._is_test(card.path):
                role = "test" if self._is_test(card.path) else ("callee" if card.key in target.calls else "caller")
                source = self._source(card, role)
                source_cost = self._tokens(source.content)
                if used + source_cost <= token_budget:
                    sources.append(source)
                    used += source_cost

        return ContextBundle(
            query=query,
            target=target,
            cards=tuple(selected_cards),
            sources=tuple(sources),
            estimated_tokens=used,
            token_budget=token_budget,
            rebuilt_files=result.snapshot.rebuilt_files,
            reused_files=result.snapshot.reused_files,
        )

    def _source(self, card: SymbolCard, role: str) -> ContextSource:
        path = (self.root / card.path).resolve(strict=True)
        content_bytes = path.read_bytes()
        revision = hashlib.sha256(content_bytes).hexdigest()
        if revision != card.revision:
            raise RuntimeError(f"symbol card became stale before source load: {card.key}")
        lines = content_bytes.decode("utf-8", errors="replace").splitlines()
        content = "\n".join(lines[card.start_line - 1 : card.end_line])
        return ContextSource(card.key, role, card.path, card.start_line, card.end_line, content)

    @staticmethod
    def _is_test(path: str) -> bool:
        return any(part.startswith("test") for part in Path(path).parts)

    @staticmethod
    def _tokens(text: str) -> int:
        # ponytail: dependency-free estimate; use the provider tokenizer when exact billing budgets matter.
        return max(1, (len(text) + 3) // 4)
