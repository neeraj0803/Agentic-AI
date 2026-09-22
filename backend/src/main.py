from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.context_api import router as context_router
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "ok"}


app.include_router(
    context_router,
    prefix="/context",
    tags=["Context Analyzer"]
)

