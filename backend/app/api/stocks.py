from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import StreamingResponse

from app.core.market_store import (
    delete_stock_data,
    get_stock_data_all,
    get_stock_data_page,
    get_stock_data_summary,
    get_symbol_info,
    list_stocks,
)
from app.models.schemas import (
    DeleteDataResponse,
    StockDataPageResponse,
    StockDataSummaryResponse,
    StockListItem,
    StockListResponse,
    DataTypeSummary,
    SyncJob,
)
from app.services import repository
from app.services.demo_engine import process_sync_job

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

_VALID_DATA_TYPES = {"daily_quotes", "financial_reports", "news_items", "announcements"}
_VALID_SOURCES = {"akshare", "tushare", "baostock"}
_SYNC_JOB_TYPES = ["history_sync", "financial_sync", "news_sync"]


@router.get("", response_model=StockListResponse)
def api_list_stocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None, max_length=100),
) -> StockListResponse:
    rows, total = list_stocks(page, page_size, search)
    items = [
        StockListItem(
            symbol=r["symbol"],
            name=r["name"],
            exchange=r["exchange"],
            industry=r.get("industry"),
            area=r.get("area"),
            listing_date=str(r["listing_date"]) if r.get("listing_date") else None,
            status=r["status"],
        )
        for r in rows
    ]
    return StockListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{symbol}/data-summary", response_model=StockDataSummaryResponse)
def api_stock_data_summary(symbol: str) -> StockDataSummaryResponse:
    info = get_symbol_info(symbol)
    name = info["name"] if info else symbol
    summaries = get_stock_data_summary(symbol)
    return StockDataSummaryResponse(
        symbol=symbol,
        name=name,
        summaries=[DataTypeSummary(**s) for s in summaries],
    )


@router.get("/{symbol}/data", response_model=StockDataPageResponse)
def api_stock_data(
    symbol: str,
    source: str = Query(...),
    data_type: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> StockDataPageResponse:
    if data_type not in _VALID_DATA_TYPES:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid data_type: {data_type}")

    rows, total, columns = get_stock_data_page(symbol, source, data_type, page, page_size)
    # Stringify date/datetime values for JSON serialization
    cleaned = [{k: str(v) if v is not None and not isinstance(v, (int, float, str, bool)) else v for k, v in row.items()} for row in rows]
    return StockDataPageResponse(rows=cleaned, total=total, page=page, page_size=page_size, columns=columns)


@router.get("/{symbol}/data/download")
def api_stock_data_download(
    symbol: str,
    source: str = Query(...),
    data_type: str = Query(...),
) -> StreamingResponse:
    if data_type not in _VALID_DATA_TYPES:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid data_type: {data_type}")

    rows, columns = get_stock_data_all(symbol, source, data_type)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: str(v) if v is not None else "" for k, v in row.items()})
    buf.seek(0)

    filename = f"{symbol}_{source}_{data_type}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/{symbol}/data", response_model=DeleteDataResponse)
def api_delete_stock_data(
    symbol: str,
    source: str = Query(...),
    data_type: str = Query(...),
) -> DeleteDataResponse:
    if data_type not in _VALID_DATA_TYPES:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid data_type: {data_type}")

    count = delete_stock_data(symbol, source, data_type)
    repository.add_operation_log(
        "stocks", "delete_data", "INFO",
        f"已删除 {symbol} / {source} / {data_type} 共 {count} 条数据。",
    )
    return DeleteDataResponse(deleted_count=count)


@router.post("/{symbol}/sync", response_model=list[SyncJob])
def api_sync_stock_by_source(
    symbol: str,
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> list[SyncJob]:
    source = payload.get("source", "")
    if source not in _VALID_SOURCES:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid source: {source}")

    created_jobs: list[SyncJob] = []
    for job_type in _SYNC_JOB_TYPES:
        job = repository.create_sync_job(
            job_type, source, "single", {"symbols": [symbol]}
        )
        repository.add_operation_log(
            "stocks", "sync", "INFO",
            f"已创建 {symbol} / {source} / {job_type} 同步任务。",
            job["id"],
        )
        background_tasks.add_task(process_sync_job, job["id"])
        created_jobs.append(SyncJob.model_validate(job))

    return created_jobs
