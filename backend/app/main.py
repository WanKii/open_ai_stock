from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.logs import router as logs_router
from app.api.settings import router as settings_router
from app.api.sources import router as sources_router
from app.api.sync import router as sync_router
from app.core.config import load_settings
from app.core.database import init_db


app = FastAPI(
    title="A股 LLM 股票分析网站 API",
    description="本地优先的 A 股智能分析后台服务。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    load_settings()


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(analysis_router)
app.include_router(sync_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(sources_router)
