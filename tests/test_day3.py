from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.triage.engine import IssueTriageEngine


DEMO_REPO = PROJECT_ROOT / "examples" / "demo_repo"


def repository_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class Day3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = IssueTriageEngine(DEMO_REPO)

    def test_five_issue_qualities_produce_structured_triage(self) -> None:
        issues = sorted((PROJECT_ROOT / "examples" / "issues").glob("*.md"))
        self.assertEqual(len(issues), 5)
        for issue in issues:
            result = self.engine.triage(issue.read_text(encoding="utf-8"))
            value = result.to_dict()
            self.assertIn(result.status, {"ready", "blocked"})
            self.assertIn("goal_contract", value)
            self.assertIn("risks", value)
            self.assertTrue(result.stop_condition)

    def test_insufficient_issue_stops_and_reports_gaps(self) -> None:
        result = self.engine.triage("It is broken.")
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.hypotheses, ())
        self.assertTrue(result.information_gaps)
        self.assertTrue(result.stop_condition.startswith("Stop"))

    def test_hypotheses_are_not_root_cause_claims_and_plan_is_verifiable(self) -> None:
        issue = (PROJECT_ROOT / "examples" / "issues" / "04-misleading-clue.md").read_text(encoding="utf-8")
        result = self.engine.triage(issue)
        self.assertEqual(result.status, "ready")
        self.assertTrue(result.hypotheses)
        self.assertTrue(all(item.status == "unverified" for item in result.hypotheses))
        self.assertTrue(all("not a confirmed root cause" in item.statement for item in result.hypotheses))
        self.assertTrue(all(step.verification for step in result.plan))

    def test_triage_is_read_only(self) -> None:
        before = repository_digest(DEMO_REPO)
        issue = (PROJECT_ROOT / "examples" / "issues" / "01-auth-login.md").read_text(encoding="utf-8")
        self.engine.triage(issue)
        self.assertEqual(repository_digest(DEMO_REPO), before)


if __name__ == "__main__":
    unittest.main()
