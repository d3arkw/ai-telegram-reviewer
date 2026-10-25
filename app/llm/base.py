from abc import ABC, abstractmethod

from app.schemas import CodeReviewResponse


class BaseLLMClient(ABC):
    @abstractmethod
    async def review(self, prompt: str) -> CodeReviewResponse:
        raise NotImplementedError
