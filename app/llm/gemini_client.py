import logging

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError

from app.config import settings
from app.llm.base import BaseLLMClient
from app.schemas import CodeReviewResponse
from app.tools.ruff_tool import RUFF_GEMINI_DECLARATION, run_ruff

logger = logging.getLogger(__name__)


def _clean_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


class GeminiLLMClient(BaseLLMClient):
    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def review(self, prompt: str, code: str = "") -> CodeReviewResponse:
        try:
            tool = types.Tool(function_declarations=[RUFF_GEMINI_DECLARATION])
            result = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[tool]),
            )

            calls = result.function_calls or []
            if calls and calls[0].name == "run_ruff" and code:
                output = await run_ruff(code)
                logger.info("TOOL run_ruff -> %.200s", output)
                response_part = types.Part.from_function_response(
                    name="run_ruff", response={"output": output}
                )
                result = await self.client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[prompt, result.candidates[0].content, response_part],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
            if not result.text:
                raise RuntimeError("Gemini вернул пустой ответ")

            try:
                return CodeReviewResponse.model_validate_json(_clean_json(result.text))
            except ValidationError:
                tidy = await self.client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=f"{prompt}\n\nТвой черновик:\n{result.text}\n\nВерни только один валидный JSON без пояснений.",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                if not tidy.text:
                    raise RuntimeError("Gemini вернул пустой ответ")
                return CodeReviewResponse.model_validate_json(_clean_json(tidy.text))

        except APIError as exc:
            raise RuntimeError(f"Ошибка Gemini API: {exc}") from exc
        except ValidationError as exc:
            raise RuntimeError(f"Gemini вернул JSON неверного формата: {exc}") from exc
