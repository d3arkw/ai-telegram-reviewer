from openai import APIError, AsyncOpenAI
from pydantic import ValidationError

from app.config import settings
from app.llm.base import BaseLLMClient
from app.schemas import CodeReviewResponse


class RouterAIClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.model = model or settings.ROUTERAI_MODEL
        self.client = AsyncOpenAI(
            api_key=api_key or settings.ROUTERAI_API_KEY,
            base_url="https://routerai.ru/api/v1",
        )

    async def review(self, prompt: str) -> CodeReviewResponse:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content

            if not content:
                raise RuntimeError("RouterAI вернул пустой ответ")
            return CodeReviewResponse.model_validate_json(content)

        except APIError as exc:
            raise RuntimeError(f"Ошибка RouterAI API: {exc}") from exc
        except ValidationError as exc:
            raise RuntimeError(
                f"RouterAI вернул JSON неверного формата: {exc}"
            ) from exc

    async def close(self) -> None:
        await self.client.close()
