from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from repopilot.evaluation.runner import EvalRunner


class Day6EvalTests(unittest.TestCase):
    def test_fixed_suite_has_exact_required_distribution(self) -> None:
        tasks = json.loads((PROJECT_ROOT / "eval" / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual(len(tasks), 20)
        self.assertEqual(Counter(task["type"] for task in tasks), {
            "research": 5, "triage": 5, "fix": 5, "safety": 3, "resilience": 2
        })
        self.assertTrue(all(task.get("expected") for task in tasks))

    def test_full_suite_runs_and_passes(self) -> None:
        summary = EvalRunner(PROJECT_ROOT).run(PROJECT_ROOT / "eval" / "tasks.json")
        self.assertEqual(summary.total, 20)
        self.assertEqual(summary.passed, 20)
        self.assertEqual(summary.failed, 0)

    def test_results_and_report_are_machine_generated(self) -> None:
        runner = EvalRunner(PROJECT_ROOT)
        summary = runner.run(PROJECT_ROOT / "eval" / "tasks.json")
        with tempfile.TemporaryDirectory() as temp:
            results = Path(temp) / "results.json"
            report = Path(temp) / "report.md"
            runner.write_outputs(summary, results, report, PROJECT_ROOT / "eval" / "mini_swe_baseline.json")
            value = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(value["passed"], 20)
            self.assertIn("20/20 passed", report.read_text(encoding="utf-8"))
            self.assertTrue(all("duration_seconds" in item for item in value["results"]))

    def test_mini_swe_baseline_contract_has_three_controlled_tasks(self) -> None:
        value = json.loads((PROJECT_ROOT / "eval" / "mini_swe_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(len(value["tasks"]), 3)
        self.assertEqual(value["status"], "blocked_no_model_credentials")
        self.assertIn("model", value["controls"])
        self.assertEqual(value["results"], [])


if __name__ == "__main__":
    unittest.main()
