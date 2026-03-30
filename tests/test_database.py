import database
import pytest


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_trades.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    database._get_engine.cache_clear()
    yield
    database._get_engine.cache_clear()


def test_save_and_load_trade(isolated_db):
    database.init_db()

    trade_id = database.save_trade(
        date="2026-03-30 09:30:00",
        ticker="SPY",
        signal="BUY",
        entry_price=100.0,
        volume=5.0,
        capital_at_risk=500.0,
    )

    trades = database.load_trades()

    assert trade_id is not None
    assert database.get_trade_count() == 1
    assert len(trades) == 1
    assert trades.iloc[0]["ticker"] == "SPY"
    assert float(trades.iloc[0]["entry_price"]) == 100.0



def test_delete_trade(isolated_db):
    database.init_db()

    trade_id = database.save_trade(
        date="2026-03-30 10:00:00",
        ticker="QQQ",
        signal="SELL",
        entry_price=200.0,
        volume=2.0,
        capital_at_risk=400.0,
    )

    deleted = database.delete_trade(trade_id)

    assert deleted is True
    assert database.get_trade_count() == 0
