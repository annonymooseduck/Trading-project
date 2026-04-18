from pathlib import Path

import pandas as pd

import database


def test_save_and_load_trade_formats_values(isolated_db):
    trade_id = database.save_trade(
        date="2026-04-13 10:00:00",
        ticker="spy",
        signal="BUY",
        entry_price=500.123,
        volume=10,
        capital_at_risk=5001.23,
    )

    trades = database.load_trades()

    assert trade_id is not None
    assert len(trades) == 1
    assert trades.iloc[0]["ticker"] == "SPY"
    assert str(trades.iloc[0]["entry_price"]).startswith("$")
    assert str(trades.iloc[0]["capital_at_risk"]).startswith("$")


def test_count_and_delete_trade(isolated_db):
    first_id = database.save_trade("2026-04-13 10:00:00", "SPY", "BUY", 500.0, 10, 5000.0)
    second_id = database.save_trade("2026-04-13 11:00:00", "QQQ", "SELL", 400.0, 5, 2000.0)

    assert first_id is not None
    assert second_id is not None
    assert database.get_trade_count() == 2

    assert database.delete_trade(first_id) is True
    assert database.get_trade_count() == 1


def test_export_trades_csv_creates_file(isolated_db):
    database.save_trade("2026-04-13 12:00:00", "MSFT", "BUY", 300.0, 4, 1200.0)
    output_name = "test_trades_export.csv"

    output_path = database.export_trades_csv(output_name)

    assert output_path is not None
    output_file = Path(output_path)
    assert output_file.exists()
    exported = pd.read_csv(output_file)
    assert not exported.empty
    output_file.unlink(missing_ok=True)


def test_load_trades_returns_empty_dataframe_on_db_error(monkeypatch):
    def raise_connect(*args, **kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr(database.sqlite3, "connect", raise_connect)
    result = database.load_trades()

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_save_trade_returns_none_on_db_error(monkeypatch):
    def raise_connect(*args, **kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr(database.sqlite3, "connect", raise_connect)
    trade_id = database.save_trade("2026-04-13", "SPY", "BUY", 100, 1, 100)

    assert trade_id is None


def test_save_and_load_settings_roundtrip(isolated_db):
    ok = database.save_settings(
        {
            "ticker": "AAPL",
            "capital": 25000,
            "max_risk_pct": 1.5,
            "bot_token": "demo-token",
            "chat_id": "123456",
        }
    )
    settings = database.load_settings()

    assert ok is True
    assert settings["ticker"] == "AAPL"
    assert settings["capital"] == "25000"
    assert settings["max_risk_pct"] == "1.5"
    assert settings["bot_token"] == "demo-token"
    assert settings["chat_id"] == "123456"


def test_save_setting_upserts_value(isolated_db):
    assert database.save_setting("ticker", "SPY") is True
    assert database.save_setting("ticker", "MSFT") is True

    settings = database.load_settings()

    assert settings["ticker"] == "MSFT"


def test_load_settings_returns_empty_dict_on_db_error(monkeypatch):
    def raise_connect(*args, **kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr(database.sqlite3, "connect", raise_connect)
    settings = database.load_settings()

    assert settings == {}
