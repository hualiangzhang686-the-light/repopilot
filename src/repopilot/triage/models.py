from __future__ import annotations

from dataclasses import asdict, dataclass

from repopilot.retrieval.evidence import EvidenceItem


@dataclass(frozen=True)
class GoalContract:
    goal: str
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    acceptance_checks: tuple[str, ...]


@dataclass(frozen=True)
class Hypothesis:
    id: str
    statement: str
    status: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class PlanStep:
    step: int
    action: str
    verification: str


@dataclass(frozen=True)
class TriageResult:
    status: str
    goal_contract: GoalContract
    evidence: tuple[EvidenceItem, ...]
    hypotheses: tuple[Hypothesis, ...]
    plan: tuple[PlanStep, ...]
    risks: tuple[str, ...]
    information_gaps: tuple[str, ...]
    stop_condition: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "goal_contract": asdict(self.goal_contract),
            "evidence": [asdict(item) for item in self.evidence],
            "hypotheses": [asdict(item) for item in self.hypotheses],
            "plan": [asdict(item) for item in self.plan],
            "risks": self.risks,
            "information_gaps": self.information_gaps,
            "stop_condition": self.stop_condition,
        }
