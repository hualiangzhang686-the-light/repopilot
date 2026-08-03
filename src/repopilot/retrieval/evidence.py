from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from repopilot.harness.permissions import RepositoryBoundary
from repopilot.retrieval.code_index import PythonAstChunker


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    path: str
    symbol: str
    kind: str
    start_line: int
    end_line: int
    reason: str
    excerpt: str


@dataclass(frozen=True)
class Claim:
    text: str
    evidence_ids: tuple[str, ...]
    confidence: str


@dataclass(frozen=True)
class EvidenceLedger:
    question: str
    evidence: tuple[EvidenceItem, ...]
    claims: tuple[Claim, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "evidence": [asdict(item) for item in self.evidence],
            "claims": [asdict(claim) for claim in self.claims],
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "EvidenceLedger":
        evidence_values = value.get("evidence", [])
        claim_values = value.get("claims", [])
        if not isinstance(evidence_values, list) or not isinstance(claim_values, list):
            raise ValueError("evidence and claims must be lists")
        return cls(
            question=str(value.get("question", "")),
            evidence=tuple(EvidenceItem(**item) for item in evidence_values if isinstance(item, dict)),
            claims=tuple(
                Claim(
                    text=str(item["text"]),
                    evidence_ids=tuple(str(value) for value in item["evidence_ids"]),
                    confidence=str(item["confidence"]),
                )
                for item in claim_values
                if isinstance(item, dict)
            ),
        )


class CitationValidator:
    def __init__(self, boundary: RepositoryBoundary) -> None:
        self.boundary = boundary

    def validate(self, ledger: EvidenceLedger) -> list[str]:
        errors: list[str] = []
        evidence_ids = [item.id for item in ledger.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append("evidence ids must be unique")
        chunks = PythonAstChunker(self.boundary.root).build()
        chunk_keys = {(chunk.path, chunk.symbol, chunk.kind, chunk.start_line, chunk.end_line) for chunk in chunks}
        for item in ledger.evidence:
            try:
                path = self.boundary.resolve(item.path, must_exist=True)
            except (PermissionError, FileNotFoundError) as exc:
                errors.append(f"{item.id}: {exc}")
                continue
            if not path.is_file():
                errors.append(f"{item.id}: citation is not a file")
                continue
            key = (item.path, item.symbol, item.kind, item.start_line, item.end_line)
            if key not in chunk_keys:
                errors.append(f"{item.id}: symbol or line range does not match the AST index")
                continue
            actual = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[item.start_line - 1 : item.end_line])
            if actual != item.excerpt:
                errors.append(f"{item.id}: excerpt does not match repository contents")
        known_ids = set(evidence_ids)
        for claim in ledger.claims:
            if not claim.evidence_ids:
                errors.append("claim has no evidence ids")
            for evidence_id in claim.evidence_ids:
                if evidence_id not in known_ids:
                    errors.append(f"claim references unknown evidence id: {evidence_id}")
        return errors
