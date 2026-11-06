from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.fix.engine import FixEngine
from repopilot.harness.trace import TraceWriter


FIX_REPO = PROJECT_ROOT / "examples" / "fix_repo"
FIX_ISSUES = PROJECT_ROOT / "examples" / "fix_issues"


def digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and "__pycache__" not in item.parts):
        value.update(path.relative_to(root).as_posix().encode())
        value.update(path.read_bytes())
    return value.hexdigest()


class Day5FixTests(unittest.TestCase):
    def run_issue(self, name: str):
        text = (FIX_ISSUES / name).read_text(encoding="utf-8")
        return FixEngine(FIX_REPO).fix(text)

    def test_three_expected_success_tasks_pass(self) -> None:
        for name in ("01-add.md", "02-slug.md", "03-timeout.md"):
            result = self.run_issue(name)
            self.assertEqual(result.status, "completed", name)
            self.assertEqual(result.review.decision, "PASS", name)

    def test_pre_and_post_test_results_are_recorded(self) -> None:
        result = self.run_issue("01-add.md")
        self.assertEqual(result.pre_test["exit_code"], 1)
        self.assertEqual(result.post_test["exit_code"], 0)

    def test_verified_result_contains_git_style_diff(self) -> None:
        result = self.run_issue("02-slug.md")
        self.assertIn("--- a/strings.py", result.diff)
        self.assertIn("+++ b/strings.py", result.diff)

    def test_failing_post_test_is_not_success(self) -> None:
        result = self.run_issue("04-test-fails.md")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.review.decision, "REVISE_ONCE")

    def test_reviewer_requests_at_most_one_revision(self) -> None:
        result = self.run_issue("04-test-fails.md")
        self.assertLessEqual(result.review.revision_requests, 1)

    def test_forbidden_patch_is_rejected_before_tests(self) -> None:
        result = self.run_issue("05-forbidden.md")
        self.assertEqual(result.status, "rejected")
        self.assertIsNone(result.pre_test)
        self.assertEqual(result.diff, "")

    def test_non_python_test_command_is_rejected(self) -> None:
        issue = """# Unsafe command for add\nThe add function is wrong.\n```repopilot-fix
{"path":"math_utils.py","old":"return left - right","new":"return left + right","test":["git","status"]}
```"""
        result = FixEngine(FIX_REPO).fix(issue)
        self.assertEqual(result.status, "rejected")
        self.assertIn("test command must use", result.stop_reason)

    def test_original_repository_is_unchanged(self) -> None:
        before = digest(FIX_REPO)
        self.run_issue("01-add.md")
        self.assertEqual(digest(FIX_REPO), before)

    def test_success_and_failure_traces_have_stop_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            success_trace = Path(temp) / "success.jsonl"
            failure_trace = Path(temp) / "failure.jsonl"
            success = FixEngine(FIX_REPO).fix(
                (FIX_ISSUES / "01-add.md").read_text(encoding="utf-8"), trace=TraceWriter(success_trace)
            )
            failure = FixEngine(FIX_REPO).fix(
                (FIX_ISSUES / "04-test-fails.md").read_text(encoding="utf-8"), trace=TraceWriter(failure_trace)
            )
            self.assertEqual(success.status, "completed")
            self.assertEqual(failure.status, "failed")
            self.assertIn('"event": "fix.stop"', success_trace.read_text(encoding="utf-8"))
            self.assertIn('"event": "fix.stop"', failure_trace.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
