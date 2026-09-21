from fastapi import FastAPI

from .api.context_api import router as context_router
app = FastAPI()


@app.get("/")
def health():
    return {"status": "ok"}


app.include_router(
    context_router,
    prefix="/context",
    tags=["Context Analyzer"]
)

