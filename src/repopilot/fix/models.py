from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PatchSpec:
    path: str
    old: str
    new: str
    test: tuple[str, ...]


@dataclass(frozen=True)
class ReviewResult:
    decision: str
    reasons: tuple[str, ...]
    revision_requests: int


@dataclass(frozen=True)
class FixResult:
    status: str
    goal: str
    patch_path: str | None
    evidence_ids: tuple[str, ...]
    pre_test: dict[str, object] | None
    post_test: dict[str, object] | None
    diff: str
    review: ReviewResult
    sandbox_isolated: bool
    stop_reason: str
    trace_path: str | None

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["review"] = asdict(self.review)
        return value
