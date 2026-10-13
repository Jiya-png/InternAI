"""Pydantic request/response models (they also drive the Swagger docs at /docs)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Education(BaseModel):
    degree: str | None = None
    institution: str | None = None
    year: int | None = None
    score: str | None = None


class ExperienceItem(BaseModel):
    title: str | None = None
    company: str | None = None
    start: str | None = None
    end: str | None = None
    duration_months: int | None = None
    is_internship: bool = False
    bullets: list[str] = []


class ProjectItem(BaseModel):
    title: str
    tech: str = ""
    bullets: list[str] = []


class SkillDetail(BaseModel):
    name: str
    category: str
    category_label: str
    count: int
    sections: list[str]


class ParsedProfile(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    links: dict[str, str | None] = {}
    summary: str = ""
    education: list[Education] = []
    experience: list[ExperienceItem] = []
    projects: list[ProjectItem] = []
    certifications: list[str] = []
    skills: list[str] = []
    skill_details: list[SkillDetail] = []
    years_of_experience: float = 0.0
    sections_found: list[str] = []
    word_count: int = 0


class RoleBrief(BaseModel):
    role_id: str
    title: str
    domain: str
    match: int


class UploadResponse(BaseModel):
    analysis_id: str
    filename: str
    parsed: ParsedProfile
    top_roles: list[RoleBrief]


class AnalysisResponse(BaseModel):
    analysis_id: str
    created_at: datetime
    filename: str
    profile: ParsedProfile
    top_roles: list[dict[str, Any]] = Field(description="Top 5 roles with explanations, radar data and courses")
    all_roles: list[RoleBrief]
    quality: dict[str, Any]
    how_calculated: str
    model_info: dict[str, Any]
    disclaimer: str


class WhatIfRequest(BaseModel):
    analysis_id: str
    role: str = Field(description="Role id (e.g. 'data_analyst') or title")
    extra_skills: list[str] = Field(default_factory=list, max_length=50)


class SkillDelta(BaseModel):
    skill: str
    delta: float


class WhatIfResponse(BaseModel):
    role_id: str
    role_title: str
    base_match: float
    new_match: float
    delta: float
    added_skills: list[str]
    unknown_skills: list[str]
    per_skill: list[SkillDelta]
    missing_required_after: list[str]
    breakdown: dict[str, float]


class RoleInfo(BaseModel):
    id: str
    title: str
    domain: str
    experience_level: str
    description: str
    required_skills: list[dict[str, Any]]
    nice_to_have: list[str]


class HealthResponse(BaseModel):
    status: str
    trained_models: bool
    embedding_backend: str | None
    n_roles: int
    n_skills: int
