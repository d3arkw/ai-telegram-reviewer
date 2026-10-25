from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from app.deps import close_llm_clients, get_code_review_service
from app.schemas import CodeReviewRequest, CodeReviewResponse
from app.services.code_review import CodeReviewService


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_llm_clients()


app = FastAPI(description="AI Reviewer", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/reviewer")
async def code_review(
    code_review_service: Annotated[CodeReviewService, Depends(get_code_review_service)],
    request: CodeReviewRequest,
) -> CodeReviewResponse:
    try:
        res = await code_review_service.create_review(
            code=request.code, level=request.level
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return res
