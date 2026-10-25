from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.review_level import ReviewLevel


class IssueSeverity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class ReviewIssue(BaseModel):
    title: str
    severity: IssueSeverity = Field(default=IssueSeverity.medium)
    category: str
    line: int | None
    description: str
    recommendation: str


class CodeReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    score: int = Field(ge=0, le=100)
    level: Literal["junior", "middle", "senior"]
    issues: list[ReviewIssue]
    improved_code: str
    junior_explanation: str
    practice_task: str


class CodeReviewRequest(BaseModel):
    code: str = Field(min_length=1)
    level: ReviewLevel = ReviewLevel.MIDDLE
