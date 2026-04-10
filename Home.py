import streamlit as st


def get_secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

st.set_page_config(
    page_title="Trading Assistant - Home",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Systematic Trading Assistant")
st.markdown("The Behavioral Firewall for Novice Investors")

with st.sidebar:
    st.header("⚙️ Global Settings")
    
    ticker = st.text_input(
        "Ticker Symbol",
        value=st.session_state.get('ticker', 'SPY'),
        key='ticker_input',
        help="Enter stock ticker (e.g., AAPL, SPY, QQQ)"
    )
    
    capital = st.number_input(
        "Total Capital ($)",
        min_value=1000,
        value=st.session_state.get('capital', 10000),
        step=500,
        key='capital_input',
        help="Your trading account capital"
    )
    
    max_risk_pct = st.slider(
        "Max Risk %",
        min_value=0.5,
        max_value=5.0,
        value=st.session_state.get('max_risk_pct', 2.0),
        step=0.5,
        key='risk_input',
        help="Maximum risk percentage per trade"
    )
    
    st.session_state.ticker = ticker
    st.session_state.capital = capital
    st.session_state.max_risk_pct = max_risk_pct
    
    st.divider()
    
    st.header("📱 Telegram Bot Setup")
    st.markdown("Configure your Telegram bot once to send notifications for all favorited stocks.")
    
    with st.expander("📖 Setup Instructions", expanded=False):
        st.markdown("""
        ### Step-by-Step Setup Guide
        
        Step 1: Create a Bot
        1. Open Telegram and search for `@BotFather`
        2. Send the message `/newbot`
        3. Follow the prompts:
           - Name your bot (e.g., "Trading Alert Bot")
           - Choose a username (must end with "bot", e.g., "trading_alerts_bot")
        4. BotFather will send you a Bot Token (looks like: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
        5. Copy and save this token—you'll need it below
        
        Step 2: Start a Chat with Your Bot ⚠️ CRITICAL STEP
        1. Click the link BotFather sends you to your new bot (or search for your bot's username)
        2. Send `/start` to your bot (this activates the chat)
        3. You should see a message like "Bot started" or it may be silent—that's OK!
        
        Step 3: Get Your Chat ID
        1. Search for `@userinfobot` on Telegram
        2. Send the message `/start`
        3. The bot will reply with your User ID (a number, e.g., `987654321`)
        4. Copy this number—it's your Chat ID
        
        Step 4: Paste Credentials Below
        1. Paste your Bot Token in the "Bot Token" field
        2. Paste your Chat ID in the "Chat ID" field
        3. Click "Test Telegram Connection" to verify
        
        ### Your Bot is Ready! 🎉
        - Notifications will be sent to your personal Telegram
        - Use the ⭐ Favorite button on the Dashboard to choose which stocks to monitor
        - One bot handles all your favorited stocks
        
        ### ⚠️ Troubleshooting "Chat not found" error?
        Make sure you sent `/start` to your bot (Step 2), not just to userinfobot!
        """)
    
    bot_token = st.text_input(
        "Bot Token",
        value=get_secret('bot_token', ''),
        type="password",
        key='bot_token_input',
        help="From @BotFather on Telegram"
    )
    
    chat_id = st.text_input(
        "Chat ID",
        value=get_secret('chat_id', ''),
        type="password",
        key='chat_id_input',
        help="From @userinfobot on Telegram"
    )
    
    st.session_state.bot_token = bot_token
    st.session_state.chat_id = chat_id
    
    if bot_token and chat_id:
        if st.button("🧪 Test Telegram Connection", key="test_tg_btn"):
            import requests
            try:
                clean_token = bot_token.strip()
                clean_chat_id = chat_id.strip()
                
                url = f"https://api.telegram.org/bot{clean_token}/sendMessage"
                payload = {
                    "chat_id": clean_chat_id,
                    "text": "✅ Test Alert\n\nYour Telegram bot is configured correctly!",
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    st.success("✅ Bot connection successful! Check your Telegram for the test message.")
                else:
                    error_data = response.json()
                    error_description = error_data.get('description', 'Unknown error')
                    st.error(f"❌ Connection failed: {error_description}")
                    st.info("💡 Common issues:\n- Bot Token incorrect\n- Chat ID incorrect\n- Extra spaces in credentials")
                    st.json(error_data) 
            except requests.exceptions.Timeout:
                st.error("❌ Request timed out. Check your internet connection.")
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Network error: {str(e)}")
            except Exception as e:
                st.error(f"❌ Unexpected error: {str(e)}")
    
    st.caption("Bot credentials saved globally—use them for all stocks!")

st.markdown("""
## What is the Behavioral Firewall?

The Behavioral Firewall is a systematic trading strategy designed to remove emotion from your investing decisions.
It uses mathematical indicators to identify mean-reversion opportunities while filtering out stocks in downtrends.

### The Core Strategy

Contrarian Mean Reversion means:
- Buy when price drops below the statistical trend (EWMA)
- Sell when price rises above the statistical trend
- But only if the stock is in a long-term uptrend (200-day SMA)

### The Safety Filters

1. Volatility Gauge (ATR) - Measures market noise
   - Green = Safe to trade (volatility < 2.5%)
   - Yellow = Caution (volatility 2.5-5%)
   - Red = Too risky (volatility > 5%)

2. Falling Knife Filter (200 SMA) - Prevents counter-trend trades
   - No buy signals if price < 200-day moving average
   - Protects you from picking falling stocks

3. Position Sizing - Intelligent share calculation
   - Based on your capital and risk tolerance
   - Formula: `(Capital x Risk%) / (Entry - Stop Loss)`
""")

st.markdown("""
## 🚀 How to Use This Website

### Step 1: Configure Settings
Use the sidebar on the left to enter:
- Your stock ticker
- Trading capital
- Risk tolerance

### Step 2: View Dashboard
Click Dashboard in the sidebar to:
- See real-time volatility analysis
- View buy/sell signals
- Check position sizing

### Step 3: Log Trades
On the Dashboard, click "Confirm & Log Trade" to:
- Save trades to your database
- Build trading history
- Track performance

### Step 4: Review History
Click Trade History in the sidebar to:
- View all logged trades
- Export to CSV
- Analyze performance
""")

st.markdown("""
## 📊 Understanding the Indicators

### ATR (Average True Range)
- What is it: A measure of how much a stock moves on average
- Why it matters: Volatile stocks need wider stop losses
- Formula: Average of (High-Low, |High-Close(prev)|, |Low-Close(prev)|) over 14 days

### EWMA (Exponential Weighted Moving Average)
- What is it: A trend line that gives more weight to recent prices
- Why it matters: Defines the "normal" price level for mean reversion
- Formula: Uses a 20-day exponential decay

### Bollinger Bands
- What is it: Upper & Lower bands = EWMA ± (2 x ATR)
- Why it matters: Prices beyond the bands are statistically unusual (likely to revert)
- Signal: Price < Lower Band = Oversold (potential buy) | Price > Upper Band = Overbought (potential sell)

### 200-day SMA (Simple Moving Average)
- What is it: The average price over the past 200 trading days (~1 year)
- Why it matters: Defines long-term trend direction
- Signal: Price > SMA = Uptrend (safe) | Price < SMA = Downtrend (avoid)
""")

st.warning("""
⚠️ DISCLAIMER: This is an educational tool, not financial advice. Past performance does not guarantee 
future results. Always do your own research and never risk more than you can afford to lose.
""")