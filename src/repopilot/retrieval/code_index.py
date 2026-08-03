from __future__ import annotations

import ast
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*|[\u4e00-\u9fff]+|\d+")
QUERY_ALIASES = {
    "登录": ("login", "auth"),
    "认证": ("authenticate", "auth"),
    "用户": ("user",),
    "会话": ("session",),
    "过期": ("expired", "expiration"),
    "超时": ("timeout",),
}


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_PATTERN.findall(text):
        lowered = raw.casefold()
        parts = [part for part in lowered.split("_") if part]
        tokens.extend(parts or [lowered])
        for chinese, aliases in QUERY_ALIASES.items():
            if chinese in raw:
                tokens.extend(aliases)
    return tokens


@dataclass(frozen=True)
class CodeChunk:
    path: str
    symbol: str
    kind: str
    start_line: int
    end_line: int
    content: str

    def as_match(self, score: float) -> dict[str, object]:
        return {
            "path": self.path,
            "symbol": self.symbol,
            "kind": self.kind,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": round(score, 6),
        }


class _DefinitionCollector(ast.NodeVisitor):
    def __init__(self, path: str, lines: list[str]) -> None:
        self.path = path
        self.lines = lines
        self.scope: list[str] = []
        self.chunks: list[CodeChunk] = []

    def _add(self, node: ast.AST, name: str, kind: str) -> None:
        start = int(getattr(node, "lineno", 1))
        end = int(getattr(node, "end_lineno", start))
        symbol = ".".join([*self.scope, name])
        self.chunks.append(CodeChunk(self.path, symbol, kind, start, end, "\n".join(self.lines[start - 1 : end])))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node, node.name, "class")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add(node, node.name, "method" if self.scope else "function")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


class PythonAstChunker:
    """Create exact line-addressable chunks for Python modules and definitions."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)

    def build(self) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        for path in sorted(self.root.rglob("*.py")):
            if any(part in {".git", "__pycache__", ".venv", "venv"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            relative = path.relative_to(self.root).as_posix()
            module = relative.removesuffix(".py").replace("/", ".")
            chunks.append(CodeChunk(relative, module, "module", 1 if lines else 0, len(lines), text))
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            collector = _DefinitionCollector(relative, lines)
            collector.visit(tree)
            chunks.extend(collector.chunks)
        return chunks


class HybridRetriever:
    """Deterministic keyword + TF-IDF vector-space retrieval (not neural embeddings)."""

    KEYWORD_WEIGHT = 0.55
    VECTOR_WEIGHT = 0.45

    def __init__(self, chunks: list[CodeChunk]) -> None:
        self.chunks = chunks
        self.documents = [Counter(tokenize(f"{chunk.path} {chunk.symbol} {chunk.content}")) for chunk in chunks]
        document_frequency: Counter[str] = Counter()
        for document in self.documents:
            document_frequency.update(document.keys())
        total = max(1, len(chunks))
        self.idf = {token: math.log((1 + total) / (1 + count)) + 1 for token, count in document_frequency.items()}

    def search(self, query: str, *, max_results: int = 5) -> list[tuple[CodeChunk, float]]:
        if max_results < 1:
            raise ValueError("max_results must be positive")
        query_terms = tokenize(query)
        if not query_terms:
            return []
        query_counts = Counter(query_terms)
        query_vector = {term: count * self.idf.get(term, 1.0) for term, count in query_counts.items()}
        query_norm = math.sqrt(sum(value * value for value in query_vector.values())) or 1.0
        unique_query = set(query_terms)
        results: list[tuple[CodeChunk, float]] = []
        for chunk, document in zip(self.chunks, self.documents, strict=True):
            matched = unique_query.intersection(document)
            keyword_score = len(matched) / len(unique_query)
            dot = sum(query_vector.get(term, 0.0) * count * self.idf.get(term, 1.0) for term, count in document.items())
            document_norm = math.sqrt(sum((count * self.idf.get(term, 1.0)) ** 2 for term, count in document.items())) or 1.0
            vector_score = dot / (query_norm * document_norm)
            leaf_symbol = chunk.symbol.rsplit(".", 1)[-1].casefold()
            symbol_terms = set(tokenize(leaf_symbol))
            exact_symbol_bonus = 0.25 if symbol_terms and symbol_terms.issubset(unique_query) else 0.0
            score = self.KEYWORD_WEIGHT * keyword_score + self.VECTOR_WEIGHT * vector_score + exact_symbol_bonus
            if score > 0:
                results.append((chunk, score))
        results.sort(key=lambda item: (-item[1], item[0].path, item[0].start_line, item[0].symbol))
        return results[:max_results]
