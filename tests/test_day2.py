from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.agent.loop import AgentLoop
from repopilot.agent.models import CodeResearchModel
from repopilot.harness.permissions import RepositoryBoundary
from repopilot.harness.trace import TraceWriter
from repopilot.retrieval.code_index import HybridRetriever, PythonAstChunker
from repopilot.retrieval.evidence import CitationValidator, EvidenceLedger
from repopilot.tools.base import ToolContext
from repopilot.tools.code import register_code_tools
from repopilot.tools.filesystem import register_read_tools
from repopilot.tools.registry import ToolRegistry


DEMO_REPO = PROJECT_ROOT / "examples" / "demo_repo"


class Day2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = RepositoryBoundary(DEMO_REPO)
        self.registry = ToolRegistry()
        register_read_tools(self.registry)
        register_code_tools(self.registry)
        self.context = ToolContext(self.boundary.root, self.boundary)

    def test_python_ast_chunks_have_exact_symbol_lines(self) -> None:
        chunks = PythonAstChunker(DEMO_REPO).build()
        login = next(chunk for chunk in chunks if chunk.symbol == "login")
        self.assertEqual(login.path, "app/auth.py")
        self.assertTrue(login.content.startswith("def login"))
        self.assertGreaterEqual(login.end_line, login.start_line)

    def test_five_ground_truth_questions_retrieve_expected_symbol(self) -> None:
        cases = json.loads((PROJECT_ROOT / "eval" / "day2_questions.json").read_text(encoding="utf-8"))
        retriever = HybridRetriever(PythonAstChunker(DEMO_REPO).build())
        self.assertEqual(len(cases), 5)
        for case in cases:
            chunk, _ = retriever.search(case["question"], max_results=1)[0]
            self.assertEqual((chunk.path, chunk.symbol), (case["path"], case["symbol"]), case["question"])

    def test_research_model_produces_a_valid_evidence_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            loop = AgentLoop(
                model=CodeResearchModel(),
                registry=self.registry,
                context=self.context,
                trace=TraceWriter(Path(temp) / "research.jsonl"),
            )
            result = loop.run("Where is the login function implemented?")
        ledger = EvidenceLedger.from_dict(result.metadata["evidence_ledger"])
        self.assertEqual(result.status, "completed")
        self.assertEqual(CitationValidator(self.boundary).validate(ledger), [])
        self.assertIn("app/auth.py", result.answer or "")
        self.assertIn("login", result.answer or "")

    def test_nonexistent_citation_is_rejected(self) -> None:
        ledger = EvidenceLedger.from_dict(
            {
                "question": "fake",
                "evidence": [{
                    "id": "ev-404", "path": "app/missing.py", "symbol": "missing", "kind": "function",
                    "start_line": 1, "end_line": 2, "reason": "fabricated", "excerpt": "def missing(): pass"
                }],
                "claims": [{"text": "fake claim", "evidence_ids": ["ev-404"], "confidence": "unsupported"}],
            }
        )
        errors = CitationValidator(self.boundary).validate(ledger)
        self.assertTrue(errors)
        self.assertIn("missing.py", errors[0])


if __name__ == "__main__":
    unittest.main()
