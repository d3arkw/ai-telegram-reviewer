import asyncio

from app import deps


def setup_function():
    deps._llm_clients.clear()


def teardown_function():
    asyncio.run(deps.close_llm_clients())


def test_router_clients_separated_by_key():
    first = deps.get_llm_client(
        "routerai", router_key="k1", router_model="qwen/qwen3.7-flash"
    )
    same = deps.get_llm_client(
        "routerai", router_key="k1", router_model="qwen/qwen3.7-flash"
    )
    other = deps.get_llm_client(
        "routerai", router_key="k2", router_model="qwen/qwen3.7-flash"
    )
    assert first is same
    assert first is not other
    assert first.model == "qwen/qwen3.7-flash"
    assert other.model == "qwen/qwen3.7-flash"


def test_gemini_client_is_singleton():
    assert deps.get_llm_client("gemini") is deps.get_llm_client("gemini")
