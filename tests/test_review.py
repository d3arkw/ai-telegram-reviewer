import pytest

from app.config import Settings
from app.models.review_level import ReviewLevel
from app.schemas import (
    CodeReviewRequest,
    CodeReviewResponse,
    IssueSeverity,
    ReviewIssue,
)
from app.services.code_review import CodeReviewService


def make_review(n: int) -> CodeReviewResponse:
    issues = [
        ReviewIssue(
            title=f"t{i}",
            severity=IssueSeverity.low,
            category="style",
            line=i,
            description="d",
            recommendation="r",
        )
        for i in range(1, n + 1)
    ]
    return CodeReviewResponse(
        summary="s",
        score=90,
        level="middle",
        issues=issues,
        improved_code="x=1",
        junior_explanation="e",
        practice_task="t",
    )


def test_prompt_keeps_braces_and_replaces_level():
    service = CodeReviewService(llm=object())
    prompt = service._build_prompt('x = {"a": 1}', ReviewLevel.MIDDLE)
    assert "__LEVEL__" not in prompt
    assert "__CODE__" not in prompt
    assert "middle" in prompt
    assert 'x = {"a": 1}' in prompt


def test_prompt_has_no_curly_quotes():
    service = CodeReviewService(llm=object())
    prompt = service._build_prompt("x=1", ReviewLevel.JUNIOR)
    assert "\u201c" not in prompt
    assert "\u201d" not in prompt


def test_render_groups_issues_by_three():
    from utils import render_review

    messages = render_review(make_review(7))
    issue_messages = [m for m in messages if "Проблема #" in m]
    assert len(issue_messages) == 3


def test_config_requires_key_for_provider():
    with pytest.raises(Exception, match="GEMINI_API_KEY"):
        Settings(
            _env_file=None,
            TELEGRAM_BOT_TOKEN="t",
            LLM_PROVIDER="gemini",
            GEMINI_API_KEY=None,
        )


def test_reviewer_maps_runtime_error_to_502():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import HTTPException

    from app.main import code_review

    service = MagicMock()
    service.create_review = AsyncMock(side_effect=RuntimeError("upstream down"))
    request = CodeReviewRequest(code="x=1", level=ReviewLevel.MIDDLE)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(code_review(service, request))
    assert exc_info.value.status_code == 502
