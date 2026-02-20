"""
Dashboard Page - Main Trading Interface

Real-time analysis with volatility gauge, signal detection, and trade logging.
This is the core trading interface where users analyze stocks and log trades.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import requests
from datetime import datetime, timedelta
from database import init_db, save_trade, load_trades

# MUST be the first Streamlit command on this page
st.set_page_config(
    page_title="Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- HELPER FUNCTIONS ---

@st.cache_data
def get_market_data(ticker, period="1y", interval="1d"):
    """Fetch and normalize OHLC market data from Yahoo Finance."""
    data = yf.download(ticker, period=period, interval=interval, progress=False)
    data = data.reset_index()
    
    # Flatten MultiIndex columns if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    # Normalize column names
    data.columns = [str(col).strip().lower() for col in data.columns]
    
    # Remove duplicates
    data = data.loc[:, ~data.columns.duplicated(keep='first')]
    
    return data

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
    
    # 1. Calculate TR (True Range)
    # True Range accounts for gaps: max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)

    # 2. Calculate ATR (Average True Range)
    # Rolling average of True Range over 14 days
    df['atr'] = df['tr'].rolling(window=atr_period).mean()

    # 3. Calculate EWMA (Exponential Weighted Moving Average)
    # Trend line that weights recent prices more heavily
    df['ewma'] = df['close'].ewm(span=ewma_period, adjust=False).mean()

    # 4. Calculate Bollinger-like Bands
    # Upper Band = EWMA + (2 × ATR) → Overbought level
    # Lower Band = EWMA - (2 × ATR) → Oversold level
    df['upper_band'] = df['ewma'] + (2 * df['atr'])
    df['lower_band'] = df['ewma'] - (2 * df['atr'])

    # 5. THE "FALLING KNIFE" FILTER
    # Calculate 200-day SMA to identify long-term trend direction
    df['sma_200'] = df['close'].rolling(window=200).mean()
    
    # Trend_up = True if price is above SMA_200 (safe/uptrend)
    # This prevents buying stocks in downtrends (falling knives)
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

def send_telegram_alert(bot_token, chat_id, message):
    """Send a Telegram message via the Bot API."""
    try:
        # Strip whitespace from credentials
        clean_token = bot_token.strip()
        clean_chat_id = chat_id.strip()
        
        url = f"https://api.telegram.org/bot{clean_token}/sendMessage"
        payload = {
            "chat_id": clean_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def check_and_alert(ticker, signal, price, bot_token, chat_id):
    """Send ticker alerts with a one-hour per-ticker cooldown."""
    # Initialize session state for alert tracking
    if 'last_alert_time' not in st.session_state:
        st.session_state.last_alert_time = {}
    
    # Check if we've alerted for this ticker recently
    current_time = datetime.now()
    last_alert = st.session_state.last_alert_time.get(ticker, None)
    
    # Send alert only if > 1 hour has passed OR this is the first alert
    if last_alert is None or (current_time - last_alert) > timedelta(hours=1):
        message = f"🚨 <b>Trading Alert: {ticker}</b>\n\n"
        message += f"Signal: <b>{signal}</b>\n"
        message += f"Price: ${price:.2f}\n"
        message += f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        if send_telegram_alert(bot_token, chat_id, message):
            # Update last alert time
            st.session_state.last_alert_time[ticker] = current_time
            return True
    
    return False

# --- PAGE TITLE ---
st.title("📈 Trading Dashboard")
st.markdown("Real-time analysis with volatility gauge, signal detection, and trade logging.")

# --- GET SETTINGS FROM SESSION STATE (set by Home.py) ---
# These are configured in Home.py and shared across all pages
ticker = st.session_state.get('ticker', 'SPY')
capital = st.session_state.get('capital', 10000)
max_risk_pct = st.session_state.get('max_risk_pct', 2.0)

# Telegram bot credentials (set globally in Home.py)
bot_token = st.session_state.get('bot_token', '')
chat_id = st.session_state.get('chat_id', '')

# Initialize favorites list if not exists
if 'favorites' not in st.session_state:
    st.session_state.favorites = []

# Allow ticker override on dashboard
with st.sidebar:
    st.header("⚙️ Dashboard Settings")
    ticker = st.text_input(
        "📍 Ticker Symbol",
        value=ticker,
        key='dashboard_ticker',
        help="Override global ticker setting"
    )
    
    # Favorite/Unfavorite button
    is_favorite = ticker.upper() in st.session_state.favorites
    favorite_label = "⭐ Unfavorite" if is_favorite else "☆ Favorite"
    
    if st.button(favorite_label, key="favorite_btn", use_container_width=True):
        if is_favorite:
            st.session_state.favorites.remove(ticker.upper())
            st.success(f"❌ {ticker.upper()} removed from favorites")
        else:
            st.session_state.favorites.append(ticker.upper())
            st.success(f"⭐ {ticker.upper()} added to favorites")
        st.rerun()
    
    # Show current favorites
    if st.session_state.favorites:
        st.caption(f"⭐ Favorites: {', '.join(st.session_state.favorites)}")
    
    st.caption("💡 Notifications only sent for favorited stocks")

# Validate ticker
if not ticker or ticker.strip() == "":
    st.error("⚠️ Please enter a valid ticker symbol in the Home page sidebar!")
    st.stop()

# --- STEP 1: DATA & CALCULATIONS ---
st.subheader("Data & Calculations")

try:
    df = get_market_data(ticker.strip().upper())
    
    # Check for insufficient data before calculations
    if len(df) < 200:
        st.warning(f"⚠️ Insufficient historical data. Only {len(df)} days available. Requires at least 200 days for SMA calculation.")
        st.info("💡 Try a different ticker with more trading history (e.g., SPY, AAPL, MSFT)")
        st.stop()
    
    df = calculate_volatility(df)
    
    # Validate we have enough data after calculations
    # Drop rows with NaN values (from indicator calculations)
    df_valid = df.dropna(subset=['atr', 'ewma', 'sma_200', 'upper_band', 'lower_band'])
    
    if len(df_valid) == 0:
        st.error(f"❌ Not enough historical data for '{ticker}'. Indicators require at least 200 days of trading history.")
        st.info("💡 Try a different ticker with more trading history (e.g., SPY, AAPL, MSFT)")
        st.stop()
    
    df = df_valid
    
except ValueError as e:
    st.error(f"❌ Invalid ticker '{ticker}': No data found")
    st.info("💡 Please check the ticker symbol and try again")
    st.stop()
except requests.exceptions.ConnectionError:
    st.error("⚠️ Network error. Please check your internet connection.")
    st.stop()
except Exception as e:
    st.error(f"❌ Error fetching data for '{ticker}': {str(e)}")
    st.stop()

# --- PRICE CHART ---
st.write("### 📈 Price Chart with Indicators")

# Create candlestick chart with Bollinger-like bands
fig_chart = go.Figure()


# Add Upper Band
fig_chart.add_trace(go.Scatter(
    x=df['date'],
    y=df['upper_band'],
    mode='lines',
    name='Upper Band',
    line=dict(color='rgba(255,0,0,0.3)', width=1),
    showlegend=True
))

# Add Lower Band with fill
fig_chart.add_trace(go.Scatter(
    x=df['date'],
    y=df['lower_band'],
    mode='lines',
    name='Lower Band',
    line=dict(color='rgba(0,255,0,0.3)', width=1),
    fill='tonexty',
    fillcolor='rgba(128,128,128,0.1)',
    showlegend=True
))

# Add EWMA (trend line)
fig_chart.add_trace(go.Scatter(
    x=df['date'],
    y=df['ewma'],
    mode='lines',
    name='EWMA (20)',
    line=dict(color='blue', width=2),
    showlegend=True
))

# Add candlestick trace
fig_chart.add_trace(go.Candlestick(
    x=df['date'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name='Price',
    increasing_line_color='green',
    decreasing_line_color='red',
    showlegend=True
))

# Update layout with better styling
fig_chart.update_layout(
    title=dict(
        text=f"{ticker.upper()} - Price Action & Indicators",
        font=dict(size=20)
    ),
    xaxis=dict(
        title="Date",
        rangeslider=dict(visible=False),  # Disable range slider
        showgrid=True
    ),
    yaxis=dict(
        title="Price ($)",
        showgrid=True
    ),
    height=600,
    hovermode='x unified',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    ),
    template="plotly_dark"
)

st.plotly_chart(fig_chart, use_container_width=True)

with st.expander("📊 View Raw Data (Last 20 days)", expanded=False):
    st.dataframe(df.tail(20), use_container_width=True)

# --- STEP 2: RISK GAUGE (Visualizing Volatility) ---
st.subheader("Volatility Risk Gauge")

latest_atr = float(df['atr'].iloc[-1])
latest_close = float(df['close'].iloc[-1])

# Determine volatility level as percentage
volatility_pct = (latest_atr / latest_close) * 100

fig_gauge = go.Figure(go.Indicator(
    mode="gauge+number+delta",
    value=float(volatility_pct),
    domain={'x': [0, 1], 'y': [0, 1]},
    title={'text': "Volatility Risk (%)"},
    delta={'reference': 2.5},
    gauge={
        'axis': {'range': [0, 10]},
        'bar': {'color': "darkblue"},
        'steps': [
            {'range': [0, 2.5], 'color': "lightgreen"},
            {'range': [2.5, 5], 'color': "yellow"},
            {'range': [5, 10], 'color': "lightcoral"}
        ],
        'threshold': {
            'line': {'color': "red", 'width': 4},
            'thickness': 0.75,
            'value': 7.5
        }
    }
))
st.plotly_chart(fig_gauge, use_container_width=True)

# Edge case warning: Ultra-low volatility
if latest_atr < 0.01:
    st.warning("⚠️ Volatility too low for reliable trading. ATR < $0.01. Position sizing may be unreliable.")

# --- STEP 3: SIGNAL LOGIC (The Core) ---
st.subheader("Trading Signal Detection")

latest_price = float(df['close'].iloc[-1])
upper_band = float(df['upper_band'].iloc[-1])
lower_band = float(df['lower_band'].iloc[-1])
ewma = float(df['ewma'].iloc[-1])
trend_up = bool(df['trend_up'].iloc[-1])
sma_200 = float(df['sma_200'].iloc[-1])

signal = None
signal_color = None

# Trend status display
trend_status = "🟢 UPTREND (Safe)" if trend_up else "🔴 DOWNTREND (Avoid)"
st.metric("Trend Status (200-day SMA)", trend_status)

# Signal logic with falling knife filter
if latest_price < lower_band and trend_up:
    # BUY only if price is below lower band AND in an uptrend
    signal = "BUY"
    signal_color = "green"
elif latest_price > upper_band:
    signal = "SELL"
    signal_color = "red"
else:
    signal = "NEUTRAL"
    signal_color = "gray"

st.metric("Current Signal", signal, delta=None)

# --- STEP 4: ACTION CARD (The Output) ---
st.subheader("Trade Action Card")

if signal in ["BUY", "SELL"]:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        entry_price = latest_price
        st.metric("Entry Price", f"${entry_price:.2f}")
    
    with col2:
        stop_loss = entry_price + (2 * latest_atr) if signal == "SELL" else entry_price - (2 * latest_atr)
        st.metric("Stop Loss", f"${stop_loss:.2f}")
    
    with col3:
        position_size = calculate_position_size(capital, max_risk_pct, entry_price, stop_loss)
        st.metric("Position Size (Shares)", position_size)
    
    st.success(f"{signal} Signal Active | Entry: ${entry_price:.2f} | Stop: ${stop_loss:.2f} | Shares: {position_size}")
else:
    st.info("⏸️ No trading signal at this time. Price is within the bands.")

# --- TELEGRAM NOTIFICATIONS ---
if bot_token and chat_id and ticker.upper() in st.session_state.favorites:
    if signal in ["BUY", "SELL"]:
        alert_sent = check_and_alert(ticker, signal, latest_price, bot_token, chat_id)
        if alert_sent:
            st.success(f"📱 Notification sent! Alert for {ticker.upper()} sent to Telegram.")
        else:
            # Check when next alert is available
            if ticker.upper() in st.session_state.get('last_alert_time', {}):
                last_alert = st.session_state.last_alert_time[ticker.upper()]
                next_alert = last_alert + timedelta(hours=1)
                time_remaining = next_alert - datetime.now()
                minutes_remaining = int(time_remaining.total_seconds() / 60)
                st.info(f"⏰ Cooldown Active: Last alert sent {60 - minutes_remaining} minutes ago. Next available in {minutes_remaining} minutes.")
elif ticker.upper() not in st.session_state.favorites:
    st.info(f"⭐ {ticker.upper()} not favorited. Click the ⭐ Favorite button in the sidebar to enable notifications for this stock.")
elif not bot_token or not chat_id:
    st.warning("⚠️ Telegram bot not configured. Set up your bot in the Home page sidebar to enable notifications.")

# --- STEP 5: TRADE LOGGING (Persistence) ---
init_db()

st.subheader("Step 5: Trade History Log")

# Manual Trade Input Section
st.write("### 📝 Log a Manual Trade")
col1, col2, col3, col4 = st.columns(4)

with col1:
    manual_ticker = st.text_input("Ticker", value=ticker, key="manual_ticker")

with col2:
    manual_signal = st.selectbox("Signal Type", ["BUY", "SELL"], key="manual_signal")

with col3:
    manual_price = st.number_input("Entry Price ($)", min_value=0.01, value=latest_price, step=0.01, key="manual_price")

with col4:
    manual_volume = st.number_input("Volume (Shares)", min_value=0.01, value=100.0, step=0.01, key="manual_volume")

# Confirm & Log Trade button
if st.button("✅ Confirm & Log Trade", key="log_trade_btn"):
    capital_at_risk = manual_price * manual_volume
    
    trade_id = save_trade(
        date=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        ticker=manual_ticker.upper(),
        signal=manual_signal,
        entry_price=manual_price,
        volume=manual_volume,
        capital_at_risk=capital_at_risk
    )
    
    if trade_id:
        st.success(f"✅ Trade #{trade_id} logged successfully! View all trades in the Trade History page.")
    else:
        st.error("❌ Error saving trade to database. Please try again.")
