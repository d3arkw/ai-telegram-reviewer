from pathlib import Path

from app.llm.base import BaseLLMClient
from app.models.review_level import ReviewLevel

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "review.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


class CodeReviewService:
    def __init__(self, llm: BaseLLMClient) -> None:
        self.llm = llm

    async def create_review(self, code: str, level: ReviewLevel):
        prompt = self._build_prompt(code, level)
        return await self.llm.review(prompt, code=code)

    def _build_prompt(self, code: str, level: ReviewLevel) -> str:
        return _PROMPT_TEMPLATE.replace("__LEVEL__", level.value).replace(
            "__CODE__", code
        )
