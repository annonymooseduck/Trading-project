"""Pure helper functions for dashboard and trade history logic."""

from __future__ import annotations

import pandas as pd

from strategy import calculate_position_size


def determine_trade_signal(latest_price, lower_band, upper_band, trend_up):
    """Return BUY, SELL, or NEUTRAL using the dashboard signal rules."""
    if latest_price < lower_band and trend_up:
        return "BUY"

    if latest_price > upper_band:
        return "SELL"

    return "NEUTRAL"


def get_action_card_labels(signal):
    """Return display labels for the trade action card."""
    if signal == "BUY":
        return {
            "price_label": "Entry Price",
            "summary_label": "BUY",
            "risk_label": "Stop Loss",
        }

    if signal == "SELL":
        return {
            "price_label": "Take Profit / Exit Price",
            "summary_label": "EXIT",
            "risk_label": "Protective Stop",
        }

    return {
        "price_label": "Price",
        "summary_label": "NEUTRAL",
        "risk_label": "Stop Loss",
    }


def build_action_card(signal, latest_price, latest_atr, capital, max_risk_pct):
    """Build the action card values for BUY/SELL signals."""
    if signal not in ["BUY", "SELL"]:
        return None

    labels = get_action_card_labels(signal)
    risk_level = latest_price - (2 * latest_atr)
    position_size = calculate_position_size(capital, max_risk_pct, latest_price, risk_level)

    return {
        **labels,
        "entry_price": latest_price,
        "risk_level": risk_level,
        "position_size": position_size,
    }


def _currency_column_to_float(series):
    return series.astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False).astype(float)


def filter_trades_dataframe(trades_df, selected_ticker="All", selected_signal="All", selected_sort="Date (Newest First)"):
    """Apply ticker, signal, and sort filters to the trade history dataframe."""
    filtered_df = trades_df.copy()

    if selected_ticker != "All":
        filtered_df = filtered_df[filtered_df["ticker"] == selected_ticker]

    if selected_signal != "All":
        filtered_df = filtered_df[filtered_df["signal"] == selected_signal]

    if selected_sort == "Date (Newest First)":
        filtered_df = filtered_df.sort_values("date", ascending=False)
    elif selected_sort == "Date (Oldest First)":
        filtered_df = filtered_df.sort_values("date", ascending=True)
    elif selected_sort == "Entry Price (High to Low)":
        filtered_df = filtered_df.assign(_sort_price=_currency_column_to_float(filtered_df["entry_price"]))
        filtered_df = filtered_df.sort_values("_sort_price", ascending=False).drop("_sort_price", axis=1)
    elif selected_sort == "Entry Price (Low to High)":
        filtered_df = filtered_df.assign(_sort_price=_currency_column_to_float(filtered_df["entry_price"]))
        filtered_df = filtered_df.sort_values("_sort_price", ascending=True).drop("_sort_price", axis=1)

    return filtered_df


def get_missing_import_columns(import_df, required_cols=None):
    """Return a list of missing CSV columns for trade history imports."""
    if required_cols is None:
        required_cols = ["date", "ticker", "signal", "entry_price", "volume", "capital_at_risk"]

    return [col for col in required_cols if col not in import_df.columns]


def calculate_total_capital_at_risk(trades_df):
    """Sum the formatted capital-at-risk column from the trade history dataframe."""
    if trades_df.empty:
        return 0.0

    return _currency_column_to_float(trades_df["capital_at_risk"]).sum()