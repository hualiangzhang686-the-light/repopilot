from __future__ import annotations

from repopilot.retrieval.code_index import HybridRetriever, PythonAstChunker
from repopilot.tools.base import ToolContext, ToolDefinition
from repopilot.tools.registry import ToolRegistry


def search_code(context: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    query = str(arguments["query"])
    max_results = int(arguments.get("max_results", 5))
    chunks = PythonAstChunker(context.repository_root).build()
    results = HybridRetriever(chunks).search(query, max_results=max_results)
    return {
        "query": query,
        "matches": [chunk.as_match(score) for chunk, score in results],
        "retrieval": {
            "chunker": "python-ast",
            "vector": "tf-idf",
            "keyword_weight": HybridRetriever.KEYWORD_WEIGHT,
            "vector_weight": HybridRetriever.VECTOR_WEIGHT,
            "neural_embeddings": False,
        },
    }


def register_code_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="search_code",
            description="Search Python AST chunks with deterministic keyword and TF-IDF scores.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
                "required": ["query"],
            },
            handler=search_code,
        )
    )
