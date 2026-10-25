from fastapi import FastAPI, Body

app = FastAPI(description="AI Reviewer")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/reviewer")
async def code_review(code: str = Body(..., media_type="text/plain")):
    return