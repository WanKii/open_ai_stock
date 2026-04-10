from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime, timezone

import pandas as pd

from app.services.adapters.akshare_adapter import AKShareAdapter


def test_fetch_announcements_prefers_individual_notice_report(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    class FakeAkshare:
        @staticmethod
        def stock_individual_notice_report(security: str, begin_date: str, end_date: str):
            calls.append((security, begin_date, end_date))
            return pd.DataFrame(
                [
                    {
                        "代码": "000001",
                        "公告标题": "平安银行公告 A",
                        "公告日期": "2026-04-10",
                        "网址": "https://example.com/a",
                    },
                    {
                        "代码": "000001",
                        "公告标题": "平安银行公告 B",
                        "公告日期": dt_date(2026, 4, 9),
                        "网址": "https://example.com/b",
                    },
                ]
            )

    monkeypatch.setattr(
        "app.services.adapters.akshare_adapter._import_akshare",
        lambda: FakeAkshare(),
    )

    rows = AKShareAdapter().fetch_announcements("000001.SH", count=2)

    assert calls
    assert calls[0][0] == "000001"
    assert len(calls[0][1]) == 8
    assert len(calls[0][2]) == 8
    assert len(rows) == 2
    assert all(row["symbol"] == "000001.SH" for row in rows)
    assert [row["title"] for row in rows] == ["平安银行公告 A", "平安银行公告 B"]
    assert rows[0]["url"] == "https://example.com/a"
    assert rows[0]["published_at"] == datetime(2026, 4, 10, tzinfo=timezone.utc)


def test_fetch_daily_quotes_falls_back_to_sina_when_eastmoney_fails(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeAkshare:
        @staticmethod
        def stock_zh_a_hist(**_kwargs):
            raise RuntimeError("eastmoney blocked")

        @staticmethod
        def stock_zh_a_daily(symbol: str, start_date: str, end_date: str, adjust: str):
            calls.append((symbol, adjust))
            assert start_date == "20260401"
            assert end_date == "20260410"
            return pd.DataFrame(
                [
                    {
                        "date": dt_date(2026, 4, 9),
                        "open": 10.1,
                        "high": 10.8,
                        "low": 10.0,
                        "close": 10.5,
                        "volume": 12345,
                        "amount": 456789,
                    },
                    {
                        "date": dt_date(2026, 4, 10),
                        "open": 10.6,
                        "high": 10.9,
                        "low": 10.2,
                        "close": 10.3,
                        "volume": 23456,
                        "amount": 567890,
                    },
                ]
            )

    monkeypatch.setattr(
        "app.services.adapters.akshare_adapter._import_akshare",
        lambda: FakeAkshare(),
    )

    rows = AKShareAdapter().fetch_daily_quotes(
        "600900.SH",
        start_date=dt_date(2026, 4, 1),
        end_date=dt_date(2026, 4, 10),
    )

    assert calls == [("sh600900", "qfq")]
    assert len(rows) == 2
    assert rows[0]["symbol"] == "600900.SH"
    assert rows[0]["trade_date"] == dt_date(2026, 4, 9)
    assert rows[0]["close"] == 10.5
    assert rows[1]["volume"] == 23456.0


def test_fetch_index_daily_falls_back_to_sina_when_eastmoney_fails(monkeypatch):
    class FakeAkshare:
        @staticmethod
        def index_zh_a_hist(**_kwargs):
            raise RuntimeError("eastmoney blocked")

        @staticmethod
        def stock_zh_index_daily(symbol: str):
            assert symbol == "sh000300"
            return pd.DataFrame(
                [
                    {"date": dt_date(2026, 4, 8), "close": 4500},
                    {"date": dt_date(2026, 4, 9), "close": 4590},
                    {"date": dt_date(2026, 4, 10), "close": 4635.9},
                ]
            )

        @staticmethod
        def stock_zh_index_daily_tx(symbol: str):
            raise AssertionError("腾讯回退不应被调用")

    monkeypatch.setattr(
        "app.services.adapters.akshare_adapter._import_akshare",
        lambda: FakeAkshare(),
    )

    rows = AKShareAdapter().fetch_index_daily(
        "000300.SH",
        start_date=dt_date(2026, 4, 9),
        end_date=dt_date(2026, 4, 10),
    )

    assert len(rows) == 2
    assert rows[0]["trade_date"] == dt_date(2026, 4, 9)
    assert rows[0]["close"] == 4590.0
    assert rows[0]["change_pct"] == 2.0
    assert rows[1]["trade_date"] == dt_date(2026, 4, 10)
    assert rows[1]["change_pct"] == round((4635.9 - 4590) / 4590 * 100, 4)
