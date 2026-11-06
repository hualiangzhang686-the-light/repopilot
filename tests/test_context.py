from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.retrieval.context import ContextManager


SERVICE = '''class TokenStore:
    def rotate(self, token: str) -> str:
        """Invalidate the old token and return a rotated token."""
        return token + "-new"


class AuthService:
    def refresh(self, token: str) -> str:
        """Rotate a refresh token."""
        store = TokenStore()
        return store.rotate(token)
'''

TEST = '''from service import AuthService


def test_refresh():
    assert AuthService().refresh("old") == "old-new"
'''


class ContextManagerTests(unittest.TestCase):
    def test_incremental_cards_graph_source_and_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = root / "repo"
            cache = root / "cache"
            repository.mkdir()
            (repository / "service.py").write_text(SERVICE, encoding="utf-8")
            (repository / "test_service.py").write_text(TEST, encoding="utf-8")
            manager = ContextManager(repository, cache)

            first = manager.search("refresh token")
            self.assertEqual(set(first.snapshot.rebuilt_files), {"service.py", "test_service.py"})
            self.assertEqual(first.matches[0].card.symbol, "AuthService.refresh")
            self.assertIn("service.py::TokenStore.rotate", first.matches[0].card.calls)

            second = manager.search("refresh token")
            self.assertEqual(set(second.snapshot.reused_files), {"service.py", "test_service.py"})
            (repository / "service.py").write_text(
                SERVICE.replace("Rotate a refresh token.", "Rotate one refresh token."),
                encoding="utf-8",
            )
            third = manager.search("refresh token")
            self.assertEqual(third.snapshot.rebuilt_files, ("service.py",))
            self.assertEqual(third.snapshot.reused_files, ("test_service.py",))

            bundle = manager.assemble("refresh token", token_budget=1000)
            self.assertEqual(bundle.target.symbol, "AuthService.refresh")
            self.assertLessEqual(bundle.estimated_tokens, bundle.token_budget)
            self.assertTrue(any(source.role == "target" and "def refresh" in source.content for source in bundle.sources))
            self.assertTrue(any(source.role == "test" and "test_refresh" in source.content for source in bundle.sources))


if __name__ == "__main__":
    unittest.main()
