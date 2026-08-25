"""Pydantic contracts shared by extraction, matching, scoring and reporting."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class MatchStatus(str, Enum):
    MATCH = "match"
    PARTIAL = "partial"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"
    NA = "N/A"


class EvidenceVerification(str, Enum):
    VERIFIED = "verified"
    UNKNOWN = "unknown"
    FAILED = "failed"


class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=1)
    match_method: str = "pending"
    similarity: float | None = Field(default=None, ge=0, le=1)
    matched_text: str | None = None
    verification_status: EvidenceVerification = EvidenceVerification.UNKNOWN


class ProjectExperience(BaseModel):
    name: str = "未命名项目"
    time: str | None = None
    role: str | None = None
    scenario: str | None = None
    tasks: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)


class WorkExperience(BaseModel):
    company: str = "未命名单位"
    role: str | None = None
    time: str | None = None
    tasks: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)


class ResumeProfile(BaseModel):
    education: str | None = None
    school: str | None = None
    school_level: str | None = None
    major: str | None = None
    status: str | None = None
    graduation_year: str | None = None
    skills: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    projects: list[ProjectExperience] = Field(default_factory=list)
    work_experiences: list[WorkExperience] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)


class JobRequirement(BaseModel):
    id: str
    dimension: str
    text: str
    priority: int = Field(default=1, ge=1, le=2)  # must=2, preferred=1
    evidence: list[SourceEvidence] = Field(default_factory=list)


class JobProfile(BaseModel):
    title: str | None = None
    duties: list[str] = Field(default_factory=list)
    requirements: list[JobRequirement] = Field(default_factory=list)


class MatchItem(BaseModel):
    requirement_id: str
    dimension: str
    requirement: str
    priority: int = Field(default=1, ge=1, le=2)
    status: MatchStatus
    resume_evidence: list[SourceEvidence] = Field(default_factory=list)
    job_evidence: list[SourceEvidence] = Field(default_factory=list)
    reason: str = ""
    project_name: str | None = None
    review_required: bool = False


class DimensionScore(BaseModel):
    dimension: str
    raw_weight: float
    normalized_weight: float = 0
    score: float = 0
    applicable_items: int = 0
    known_items: int = 0


class ScoreBreakdown(BaseModel):
    total_score: float = 0
    completeness: float = 0
    dimensions: list[DimensionScore] = Field(default_factory=list)
    hard_gate: str = "review"
    formula: str = ""


class AnalysisReport(BaseModel):
    resume: ResumeProfile
    job: JobProfile
    matches: list[MatchItem]
    scoring: ScoreBreakdown
    risks: list[MatchItem] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
