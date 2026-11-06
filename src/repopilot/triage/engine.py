from __future__ import annotations

from pathlib import Path

from repopilot.harness.permissions import RepositoryBoundary
from repopilot.harness.trace import TraceWriter
from repopilot.retrieval.code_index import HybridRetriever, PythonAstChunker, tokenize
from repopilot.retrieval.evidence import EvidenceItem
from repopilot.triage.models import GoalContract, Hypothesis, PlanStep, TriageResult


class IssueTriageEngine:
    """Turn issue text into an evidence-linked plan without modifying the repository."""

    def __init__(self, repository_root: Path) -> None:
        self.boundary = RepositoryBoundary(repository_root)

    def triage(self, issue_text: str, *, trace: TraceWriter | None = None) -> TriageResult:
        writer = trace or TraceWriter.disabled()
        text = issue_text.strip()
        goal = self._goal(text)
        writer.emit("triage.start", step=0, data={"goal": goal})
        if self._is_insufficient(text):
            result = self._blocked(goal, "The issue does not contain enough observable behavior or code context.")
            writer.emit("triage.stop", step=0, data={"status": result.status, "gaps": result.information_gaps})
            return result

        chunks = PythonAstChunker(self.boundary.root).build()
        matches = HybridRetriever(chunks).search(text, max_results=3)
        if not matches:
            result = self._blocked(goal, "No repository evidence matched the issue text.")
            writer.emit("triage.stop", step=1, data={"status": result.status, "gaps": result.information_gaps})
            return result

        evidence = tuple(
            EvidenceItem(
                id=f"ev-{index}",
                path=chunk.path,
                symbol=chunk.symbol,
                kind=chunk.kind,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                reason=f"Candidate {index} from hybrid retrieval; score={score:.4f}.",
                excerpt=chunk.content,
            )
            for index, (chunk, score) in enumerate(matches, start=1)
        )
        writer.emit(
            "triage.evidence",
            step=1,
            data={"candidates": [{"id": item.id, "path": item.path, "symbol": item.symbol} for item in evidence]},
        )
        hypotheses = tuple(
            Hypothesis(
                id=f"hyp-{index}",
                statement=f"{item.symbol} may be related to the report; it is a candidate, not a confirmed root cause.",
                status="unverified",
                evidence_ids=(item.id,),
            )
            for index, item in enumerate(evidence, start=1)
        )
        paths = tuple(dict.fromkeys(item.path for item in evidence))
        contract = GoalContract(
            goal=goal,
            in_scope=paths,
            out_of_scope=("repository-external paths", "code changes during triage", "uncited root-cause claims"),
            acceptance_checks=(
                "reported behavior is reproducible",
                "one hypothesis is confirmed or all are falsified",
                "a regression check is defined before implementation",
            ),
        )
        plan = (
            PlanStep(1, "Reproduce the reported behavior without changing code.", "Capture exact inputs, actual output, and expected output."),
            PlanStep(2, "Inspect each cited candidate and test the linked hypothesis.", "Record evidence that confirms or falsifies every hypothesis."),
            PlanStep(3, "Design the smallest fix only after a cause is confirmed.", "Run the reproduction plus a focused regression test and compare results."),
        )
        result = TriageResult(
            status="ready",
            goal_contract=contract,
            evidence=evidence,
            hypotheses=hypotheses,
            plan=plan,
            risks=(
                "retrieval relevance is not proof of causality",
                "issue text may omit environment or reproduction details",
            ),
            information_gaps=(),
            stop_condition="Stop before code modification if reproduction or hypothesis evidence is still missing.",
        )
        writer.emit("triage.stop", step=2, data={"status": result.status, "hypotheses": len(result.hypotheses)})
        return result

    @staticmethod
    def _goal(text: str) -> str:
        for line in text.splitlines():
            cleaned = line.strip().lstrip("#*- ").strip()
            if cleaned:
                return cleaned
        return "Clarify the issue"

    @staticmethod
    def _is_insufficient(text: str) -> bool:
        return len(text) < 20 or len(set(tokenize(text))) < 3

    @staticmethod
    def _blocked(goal: str, gap: str) -> TriageResult:
        return TriageResult(
            status="blocked",
            goal_contract=GoalContract(
                goal=goal,
                in_scope=(),
                out_of_scope=("code changes during triage", "unsupported conclusions"),
                acceptance_checks=("obtain a reproducible expected-versus-actual behavior",),
            ),
            evidence=(),
            hypotheses=(),
            plan=(),
            risks=("acting on an underspecified issue could change the wrong behavior",),
            information_gaps=(gap, "Provide reproduction steps, expected result, actual result, and relevant environment details."),
            stop_condition="Stop: insufficient evidence to produce an implementation plan.",
        )
