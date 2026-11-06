from __future__ import annotations

from repopilot.retrieval.code_index import HybridRetriever
from repopilot.retrieval.context import ContextManager
from repopilot.tools.base import ToolContext, ToolDefinition
from repopilot.tools.registry import ToolRegistry


def search_code(context: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    query = str(arguments["query"])
    max_results = int(arguments.get("max_results", 5))
    result = ContextManager(context.repository_root, context.symbol_cache_root).search(
        query, max_results=max_results
    )
    return {
        "query": query,
        "matches": [match.card.as_match(match.score) for match in result.matches],
        "retrieval": {
            "chunker": "python-ast-symbol-cards",
            "vector": "tf-idf",
            "keyword_weight": HybridRetriever.KEYWORD_WEIGHT,
            "vector_weight": HybridRetriever.VECTOR_WEIGHT,
            "neural_embeddings": False,
            "summary_source": "docstring-or-signature",
            "cache": {
                "rebuilt_files": list(result.snapshot.rebuilt_files),
                "reused_files": list(result.snapshot.reused_files),
            },
        },
    }


def register_code_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="search_code",
            description="Search versioned Python symbol cards; use read_file before making claims or edits.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
                "required": ["query"],
            },
            handler=search_code,
        )
    )
