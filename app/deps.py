from app.config import settings
from app.llm.base import BaseLLMClient
from app.llm.gemini_client import GeminiLLMClient
from app.llm.RouterAIClient import RouterAIClient
from app.services.code_review import CodeReviewService

_llm_clients: dict[str, BaseLLMClient] = {}


def get_llm_client() -> BaseLLMClient:
    if settings.LLM_PROVIDER == "gemini":
        client = _llm_clients.get("gemini")
        if client is None:
            client = GeminiLLMClient()
            _llm_clients["gemini"] = client
        return client
    elif settings.LLM_PROVIDER == "routerai":
        client = _llm_clients.get("routerai")
        if client is None:
            client = RouterAIClient()
            _llm_clients["routerai"] = client
        return client
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")


def get_code_review_service() -> CodeReviewService:
    return CodeReviewService(get_llm_client())


async def close_llm_clients() -> None:
    for client in _llm_clients.values():
        close = getattr(client, "close", None)
        if callable(close):
            await close()
    _llm_clients.clear()
