from app.config import settings
from app.llm.base import BaseLLMClient
from app.llm.gemini_client import GeminiLLMClient
from app.llm.RouterAIClient import RouterAIClient
from app.services.code_review import CodeReviewService

_llm_clients: dict[str, BaseLLMClient] = {}


def get_llm_client(
    provider: str | None = None,
    router_key: str | None = None,
    router_model: str | None = None,
) -> BaseLLMClient:
    resolved = provider or settings.LLM_PROVIDER
    if resolved == "gemini":
        client = _llm_clients.get("gemini")
        if client is None:
            client = GeminiLLMClient()
            _llm_clients["gemini"] = client
        return client
    elif resolved == "routerai":
        key = router_key or settings.ROUTERAI_API_KEY
        model = router_model or settings.ROUTERAI_MODEL
        cache_key = f"routerai:{model}:{key}"
        client = _llm_clients.get(cache_key)
        if client is None:
            client = RouterAIClient(api_key=key, model=model)
            _llm_clients[cache_key] = client
        return client
    else:
        raise ValueError(f"Unsupported LLM provider: {resolved}")


def get_code_review_service(
    provider: str | None = None,
    router_key: str | None = None,
    router_model: str | None = None,
) -> CodeReviewService:
    return CodeReviewService(get_llm_client(provider, router_key, router_model))


async def close_llm_clients() -> None:
    for client in _llm_clients.values():
        close = getattr(client, "close", None)
        if callable(close):
            await close()
    _llm_clients.clear()
