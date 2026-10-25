from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError

from app.config import settings
from app.llm.base import BaseLLMClient
from app.schemas import CodeReviewResponse


class GeminiLLMClient(BaseLLMClient):
    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def review(self, prompt: str) -> CodeReviewResponse:
        try:
            result = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            if not result.text:
                raise RuntimeError("Gemini вернул пустой ответ")

            return CodeReviewResponse.model_validate_json(result.text)

        except APIError as exc:
            raise RuntimeError(f"Ошибка Gemini API: {exc}") from exc
        except ValidationError as exc:
            raise RuntimeError(f"Gemini вернул JSON неверного формата: {exc}") from exc
