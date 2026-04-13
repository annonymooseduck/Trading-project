"""Pure strategy calculation helpers used by the dashboard and tests."""


def calculate_volatility(df, atr_period=14, ewma_period=20):
    """Compute ATR, EWMA, bands, SMA-200, and trend filter columns."""
    df = df.copy().reset_index(drop=True)

    # Normalize columns
    df.columns = df.columns.str.strip()
    df.columns = [col.lower() for col in df.columns]
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    # Validate required columns
    required_cols = ['close', 'high', 'low']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}. Available columns: {list(df.columns)}")

    # Calculate True Range
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)

    # Calculate Average True Range
    df['atr'] = df['tr'].rolling(window=atr_period).mean()

    # Calculate EWMA (Exponential Weighted Moving Average)
    df['ewma'] = df['close'].ewm(span=ewma_period, adjust=False).mean()

    # Calculate Bollinger-like Bands
    df['upper_band'] = df['ewma'] + (2 * df['atr'])
    df['lower_band'] = df['ewma'] - (2 * df['atr'])

    # Calculate 200-day SMA for falling knife filter
    df['sma_200'] = df['close'].rolling(window=200).mean()

    # Trend up = True if price is above SMA_200 (safe/uptrend)
    df['trend_up'] = (df['close'] > df['sma_200']).fillna(False).astype(bool)

    # Cleanup temporary columns
    df.drop(['h-l', 'h-pc', 'l-pc', 'tr'], axis=1, inplace=True)

    return df


def calculate_position_size(capital, risk_pct, entry_price, stop_loss):
    """Calculate risk-based position size from entry and stop distance."""
    risk_amount = capital * (risk_pct / 100)
    price_risk = abs(entry_price - stop_loss)

    # Edge case: Zero or near-zero price risk
    if price_risk < 0.01:
        return 0

    shares = int(risk_amount / price_risk)

    # Edge case: Cap position size to available capital
    if shares * entry_price > capital:
        shares = int(capital / entry_price)

    return shares