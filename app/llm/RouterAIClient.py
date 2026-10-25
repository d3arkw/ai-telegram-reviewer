import logging

from openai import APIError, AsyncOpenAI
from pydantic import ValidationError

from app.config import settings
from app.llm.base import BaseLLMClient
from app.schemas import CodeReviewResponse
from app.tools.ruff_tool import RUFF_OPENAI_TOOL, run_ruff

logger = logging.getLogger(__name__)


class RouterAIClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.model = model or settings.ROUTERAI_MODEL
        self.client = AsyncOpenAI(
            api_key=api_key or settings.ROUTERAI_API_KEY,
            base_url="https://routerai.ru/api/v1",
        )

    async def review(self, prompt: str, code: str = "") -> CodeReviewResponse:
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[RUFF_OPENAI_TOOL],
            )
            message = response.choices[0].message

            calls = message.tool_calls or []
            if calls and calls[0].function.name == "run_ruff" and code:
                output = await run_ruff(code)
                logger.info("TOOL run_ruff -> %.200s", output)
                messages = [
                    {"role": "user", "content": prompt},
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": calls[0].id,
                                "type": "function",
                                "function": {
                                    "name": "run_ruff",
                                    "arguments": calls[0].function.arguments,
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "tool_call_id": calls[0].id,
                        "content": output,
                    },
                ]
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
            else:
                content = message.content

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
