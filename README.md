# Trading Assistant

A Streamlit-based trading assistant designed to help novice investors follow a systematic, rules-based approach to trading. The application combines live market data, volatility analysis, signal generation, risk-based position sizing, trade logging, and trade history management in one dashboard-driven workflow.

## Features

- Live stock charting with price indicators and volatility bands
- Buy, sell, or neutral signal generation based on market conditions
- Automatic stop-loss and position sizing calculations tied to capital and risk settings
- Global settings for ticker, total capital, maximum risk per trade, and Telegram credentials
- Trade logging into a local SQLite database
- Trade history dashboard with filtering, sorting, export, and import via CSV
- Telegram notification setup for selected favorite stocks
- Persistence for settings and trades across sessions
- Automated test coverage for strategy, helper, and database logic

## Project Structure

- `Home.py` - landing page and global settings setup
- `pages/Dashboard.py` - live analysis dashboard and trade logging
- `pages/Trade_History.py` - trade review, filtering, CSV import/export
- `strategy.py` - volatility and position-sizing calculations
- `app_helpers.py` - pure helper functions used by the UI and tests
- `database.py` - SQLite persistence for trades and app settings
- `tests/` - unit tests for the core modules

## Tech Stack

- Python
- Streamlit
- Pandas
- Plotly
- yfinance
- SQLite
- Pytest
- GitHub Actions

## Getting Started

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
streamlit run Home.py
```

## Testing

Run the automated test suite with:

```bash
pytest
```

## Notes

- The app uses a local SQLite database to store trades and saved settings.
- Telegram alerts require a bot token and chat ID.
- The project is designed for learning and validation rather than live production trading.

## Future Improvements

- Add stronger multi-user support and authentication
- Expand backtesting and performance analytics
- Improve fault tolerance for external data feed failures
- Move storage to a cloud-hosted database for broader deployment