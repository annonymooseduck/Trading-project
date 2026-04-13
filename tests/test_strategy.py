import pandas as pd
import pytest

from strategy import calculate_position_size, calculate_volatility


def test_calculate_position_size_normal_case():
    shares = calculate_position_size(capital=10000, risk_pct=2, entry_price=100, stop_loss=95)
    assert shares == 40


def test_calculate_position_size_low_price_risk_returns_zero():
    shares = calculate_position_size(capital=10000, risk_pct=2, entry_price=100, stop_loss=100)
    assert shares == 0


def test_calculate_position_size_caps_to_capital():
    shares = calculate_position_size(capital=1000, risk_pct=50, entry_price=100, stop_loss=99.5)
    assert shares == 10


def test_calculate_volatility_adds_expected_columns():
    rows = 220
    base = pd.Series(range(1, rows + 1), dtype=float)
    df = pd.DataFrame(
        {
            "close": base + 100,
            "high": base + 101,
            "low": base + 99,
        }
    )

    result = calculate_volatility(df)

    for col in ["atr", "ewma", "upper_band", "lower_band", "sma_200", "trend_up"]:
        assert col in result.columns
    assert result["trend_up"].dtype == bool


def test_calculate_volatility_missing_columns_raises():
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError):
        calculate_volatility(df)
