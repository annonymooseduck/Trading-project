import pandas as pd

from app_helpers import (
    build_action_card,
    calculate_total_capital_at_risk,
    determine_trade_signal,
    filter_trades_dataframe,
    get_action_card_labels,
    get_missing_import_columns,
)


def test_determine_trade_signal_buy_when_below_lower_band_and_uptrend():
    signal = determine_trade_signal(latest_price=95, lower_band=100, upper_band=120, trend_up=True)

    assert signal == "BUY"


def test_determine_trade_signal_sell_when_above_upper_band():
    signal = determine_trade_signal(latest_price=130, lower_band=100, upper_band=120, trend_up=True)

    assert signal == "SELL"


def test_determine_trade_signal_neutral_when_conditions_not_met():
    signal = determine_trade_signal(latest_price=110, lower_band=100, upper_band=120, trend_up=False)

    assert signal == "NEUTRAL"


def test_get_action_card_labels_reflect_long_only_ui():
    buy_labels = get_action_card_labels("BUY")
    sell_labels = get_action_card_labels("SELL")

    assert buy_labels == {
        "price_label": "Entry Price",
        "summary_label": "BUY",
        "risk_label": "Stop Loss",
    }
    assert sell_labels == {
        "price_label": "Take Profit / Exit Price",
        "summary_label": "EXIT",
        "risk_label": "Protective Stop",
    }


def test_build_action_card_returns_expected_values():
    action_card = build_action_card(
        signal="BUY",
        latest_price=252.18,
        latest_atr=10.0,
        capital=10000,
        max_risk_pct=2.0,
    )

    assert action_card["price_label"] == "Entry Price"
    assert action_card["entry_price"] == 252.18
    assert action_card["risk_label"] == "Stop Loss"
    assert action_card["risk_level"] == 232.18
    assert action_card["position_size"] == 10


def test_filter_trades_dataframe_filters_and_sorts():
    trades_df = pd.DataFrame(
        {
            "date": ["2026-04-13 10:00:00", "2026-04-14 10:00:00", "2026-04-12 10:00:00"],
            "ticker": ["SPY", "AAPL", "SPY"],
            "signal": ["BUY", "SELL", "BUY"],
            "entry_price": ["$100.00", "$250.00", "$150.00"],
            "volume": [10, 5, 8],
            "capital_at_risk": ["$1000.00", "$1250.00", "$1200.00"],
        }
    )

    filtered_df = filter_trades_dataframe(
        trades_df,
        selected_ticker="SPY",
        selected_signal="BUY",
        selected_sort="Entry Price (Low to High)",
    )

    assert list(filtered_df["ticker"]) == ["SPY", "SPY"]
    assert list(filtered_df["entry_price"]) == ["$100.00", "$150.00"]


def test_get_missing_import_columns_detects_gaps():
    import_df = pd.DataFrame(
        {
            "date": ["2026-04-13"],
            "ticker": ["SPY"],
            "signal": ["BUY"],
            "entry_price": [100.0],
        }
    )

    missing_cols = get_missing_import_columns(import_df)

    assert missing_cols == ["volume", "capital_at_risk"]


def test_calculate_total_capital_at_risk_sums_formatted_values():
    trades_df = pd.DataFrame(
        {
            "capital_at_risk": ["$1,000.00", "$250.50", "$749.50"],
        }
    )

    total = calculate_total_capital_at_risk(trades_df)

    assert total == 2000.0
