from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime, timezone

import pandas as pd

from app.services.adapters.akshare_adapter import AKShareAdapter


def test_fetch_announcements_uses_market_notice_report_and_filters_symbol(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeAkshare:
        @staticmethod
        def stock_notice_report(symbol: str, date: str):
            calls.append((symbol, date))
            return pd.DataFrame(
                [
                    {
                        "代码": "000001",
                        "公告标题": "平安银行公告 A",
                        "公告日期": "2026-04-10",
                        "网址": "https://example.com/a",
                    },
                    {
                        "代码": "600519",
                        "公告标题": "贵州茅台公告",
                        "公告日期": "2026-04-10",
                        "网址": "https://example.com/b",
                    },
                    {
                        "代码": "000001",
                        "公告标题": "平安银行公告 B",
                        "公告日期": dt_date(2026, 4, 9),
                        "网址": "https://example.com/c",
                    },
                ]
            )

    monkeypatch.setattr(
        "app.services.adapters.akshare_adapter._import_akshare",
        lambda: FakeAkshare(),
    )

    rows = AKShareAdapter().fetch_announcements("000001.SH", count=2)

    assert len(rows) == 2
    assert all(row["symbol"] == "000001.SH" for row in rows)
    assert [row["title"] for row in rows] == ["平安银行公告 A", "平安银行公告 B"]
    assert rows[0]["url"] == "https://example.com/a"
    assert rows[0]["published_at"] == datetime(2026, 4, 10, tzinfo=timezone.utc)
    assert calls
    assert calls[0][0] == "全部"
    assert len(calls[0][1]) == 8
