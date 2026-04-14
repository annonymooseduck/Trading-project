import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import requests
from datetime import datetime, timedelta
from database import init_db, save_trade, load_trades
from app_helpers import build_action_card, determine_trade_signal
from strategy import calculate_volatility, calculate_position_size


def get_secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

st.set_page_config(
    page_title="Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_data
def get_market_data(ticker, period="1y", interval="1d"):
    """Fetch and normalize OHLC market data from Yahoo Finance."""
    data = yf.download(ticker, period=period, interval=interval, progress=False)
    data = data.reset_index()
    
    # Flatten MultiIndex columns if exist otherwise errors
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    # Normalize column names
    data.columns = [str(col).strip().lower() for col in data.columns]
    
    # Remove dupes
    data = data.loc[:, ~data.columns.duplicated(keep='first')]
    
    return data

def send_telegram_alert(bot_token, chat_id, message):
    """Send a Telegram message via the Bot API."""
    try:
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
    
    # Send alert only if 1 hour has passed or this is the first alert
    if last_alert is None or (current_time - last_alert) > timedelta(hours=1):
        message = f"🚨 <b>Trading Alert: {ticker}</b>\n\n"
        message += f"Signal: <b>{signal}</b>\n"
        message += f"Price: ${price:.2f}\n"
        message += f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        if send_telegram_alert(bot_token, chat_id, message):
            st.session_state.last_alert_time[ticker] = current_time
            return True
    
    return False

st.title("📈 Trading Dashboard")
st.markdown("Real-time analysis with volatility gauge, signal detection, and trade logging.")

# Get settings from session state (set by Home.py)
ticker = st.session_state.get('ticker', 'SPY')
capital = st.session_state.get('capital', 10000)
max_risk_pct = st.session_state.get('max_risk_pct', 2.0)

# Telegram bot credentials (read from secrets on Streamlit Cloud, or session state locally)
bot_token = get_secret('bot_token', st.session_state.get('bot_token', ''))
chat_id = get_secret('chat_id', st.session_state.get('chat_id', ''))

# Initialize favorites list
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

st.write("### 📈 Price Chart with Indicators")

fig_chart = go.Figure()


fig_chart.add_trace(go.Scatter(
    x=df['date'],
    y=df['upper_band'],
    mode='lines',
    name='Upper Band',
    line=dict(color='rgba(255,0,0,0.3)', width=1),
    showlegend=True
))

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

# changing layout of chart
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

# Risk gauge
st.subheader("Volatility Risk Gauge")

latest_atr = float(df['atr'].iloc[-1])
latest_close = float(df['close'].iloc[-1])

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

# Edge case: Ultra-low volatility
if latest_atr < 0.01:
    st.warning("⚠️ Volatility too low for reliable trading. ATR < $0.01. Position sizing may be unreliable.")

# Signal logic
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
signal = determine_trade_signal(latest_price, lower_band, upper_band, trend_up)
signal_color = "green" if signal == "BUY" else "red" if signal == "SELL" else "gray"

st.metric("Current Signal", signal, delta=None)


st.subheader("Trade Action Card")

if signal in ["BUY", "SELL"]:
    action_card = build_action_card(signal, latest_price, latest_atr, capital, max_risk_pct)

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(action_card["price_label"], f"${action_card['entry_price']:.2f}")
    
    with col2:
        st.metric(action_card["risk_label"], f"${action_card['risk_level']:.2f}")
    
    with col3:
        st.metric("Position Size (Shares)", action_card["position_size"])
    
    st.success(
        f"{action_card['summary_label']} Signal Active | {action_card['price_label']}: ${action_card['entry_price']:.2f} | "
        f"{action_card['risk_label']}: ${action_card['risk_level']:.2f} | Shares: {action_card['position_size']}"
    )
else:
    st.info("⏸️ No trading signal at this time. Price is within the bands.")

# Telegram alerts
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

# Trade History Log
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