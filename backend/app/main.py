from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.analysis import router as analysis_router
from app.api.logs import router as logs_router
from app.api.settings import router as settings_router
from app.api.sources import router as sources_router
from app.api.stocks import router as stocks_router
from app.api.sync import router as sync_router
from app.core.config import load_settings
from app.core.database import init_db
from app.core.market_store import init_market_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    init_market_store()
    load_settings()
    yield


app = FastAPI(
    title="A股 LLM 股票分析网站 API",
    description="本地优先的 A 股智能分析后端服务。",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后重试。",
            "detail": str(exc) if app.debug else None,
        },
    )


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(analysis_router)
app.include_router(sync_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(sources_router)
app.include_router(stocks_router)
