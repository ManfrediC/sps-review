from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field


DataGranularity = Literal["individual-level", "group-level", "both", "unclear"]
CountConfidence = Literal["high", "medium", "low"]


class LocalCountPossibility(BaseModel):
    n_spsd_patients: int = Field(..., ge=0, description="Possible extractable SPS-spectrum patient count.")
    evidence_span: str = Field(..., description="Quote or local span supporting this possibility.")
    data_granularity: DataGranularity = Field(..., description="Whether the evidence is individual-level or group-level.")
    confidence: CountConfidence = Field(..., description="Confidence in this possible count.")
    rationale_short: str = Field(
        default="",
        description="Short explanation of why this possibility is plausible.",
    )


class LocalCountDecisionOutput(BaseModel):
    n_spsd_patients: int = Field(..., ge=0, description="Best local-model estimate of the extractable SPS-spectrum count.")
    evidence_span: str = Field(..., description="Primary evidence span for the selected count.")
    data_granularity: DataGranularity = Field(..., description="Whether the selected evidence is individual-level or group-level.")
    confidence: CountConfidence = Field(..., description="Confidence in the selected count.")
    needs_review: bool = Field(..., description="Whether the row should be treated as requiring manual or stronger-model review.")
    reasoning_short: str = Field(..., description="Brief explanation for the selected count.")
    possibilities: list[LocalCountPossibility] = Field(
        default_factory=list,
        description="Optional competing possibilities when the evidence is genuinely ambiguous.",
    )


@dataclass(frozen=True)
class LocalModelCallResult:
    model_id: str
    status: str
    raw_output: str
    response_payload: dict[str, Any]
    parsed: LocalCountDecisionOutput | None = None
    error: str = ""
    duration_seconds: float = 0.0
