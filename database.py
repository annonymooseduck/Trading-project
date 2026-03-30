"""Database operations for trade persistence with Postgres-first configuration."""

import logging
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "trades.db"


def _get_database_url():
    """Get DATABASE_URL from environment or Streamlit secrets, with SQLite fallback."""
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    try:
        import streamlit as st

        return st.secrets.get("DATABASE_URL", st.secrets.get("database_url", ""))
    except Exception:
        return ""


def _normalize_database_url(database_url):
    """Normalize URL for SQLAlchemy and psycopg compatibility."""
    if not database_url:
        return f"sqlite:///{DB_PATH}"

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return database_url


@lru_cache(maxsize=1)
def _get_engine():
    db_url = _normalize_database_url(_get_database_url())
    logger.info("Using database backend: %s", "Postgres" if "postgresql" in db_url else "SQLite")
    return create_engine(db_url, pool_pre_ping=True)


def _log_audit(conn, action, trade_id=None, details=""):
    conn.execute(
        text(
            """
            INSERT INTO audit_log (action, trade_id, details)
            VALUES (:action, :trade_id, :details)
            """
        ),
        {"action": action, "trade_id": trade_id, "details": details},
    )


def init_db():
    """Initialize required tables in the configured database."""
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            dialect = conn.engine.dialect.name

            if dialect == "postgresql":
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS trades (
                            id SERIAL PRIMARY KEY,
                            date TEXT NOT NULL,
                            ticker VARCHAR(16) NOT NULL,
                            signal VARCHAR(8) NOT NULL,
                            entry_price DOUBLE PRECISION NOT NULL,
                            volume DOUBLE PRECISION NOT NULL,
                            capital_at_risk DOUBLE PRECISION NOT NULL,
                            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS audit_log (
                            id SERIAL PRIMARY KEY,
                            action VARCHAR(64) NOT NULL,
                            trade_id INTEGER,
                            details TEXT,
                            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS trades (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT NOT NULL,
                            ticker TEXT NOT NULL,
                            signal TEXT NOT NULL,
                            entry_price REAL NOT NULL,
                            volume REAL NOT NULL,
                            capital_at_risk REAL NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS audit_log (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            action TEXT NOT NULL,
                            trade_id INTEGER,
                            details TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
    except Exception:
        logger.exception("Failed to initialize database")


def save_trade(date, ticker, signal, entry_price, volume, capital_at_risk):
    """Insert a trade record and return its ID."""
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            dialect = conn.engine.dialect.name
            if dialect == "postgresql":
                result = conn.execute(
                    text(
                        """
                        INSERT INTO trades (date, ticker, signal, entry_price, volume, capital_at_risk)
                        VALUES (:date, :ticker, :signal, :entry_price, :volume, :capital_at_risk)
                        RETURNING id
                        """
                    ),
                    {
                        "date": date,
                        "ticker": ticker.upper(),
                        "signal": signal,
                        "entry_price": float(entry_price),
                        "volume": float(volume),
                        "capital_at_risk": float(capital_at_risk),
                    },
                )
                trade_id = result.scalar_one()
            else:
                result = conn.execute(
                    text(
                        """
                        INSERT INTO trades (date, ticker, signal, entry_price, volume, capital_at_risk)
                        VALUES (:date, :ticker, :signal, :entry_price, :volume, :capital_at_risk)
                        """
                    ),
                    {
                        "date": date,
                        "ticker": ticker.upper(),
                        "signal": signal,
                        "entry_price": float(entry_price),
                        "volume": float(volume),
                        "capital_at_risk": float(capital_at_risk),
                    },
                )
                trade_id = result.lastrowid

            _log_audit(conn, action="trade_saved", trade_id=trade_id, details=f"ticker={ticker.upper()},signal={signal}")
            return trade_id
    except Exception:
        logger.exception("Error saving trade")
        return None


def load_trades():
    """Query and return all trades with raw numeric values."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            df = pd.read_sql_query(text("SELECT * FROM trades ORDER BY date DESC"), conn)

        if df.empty:
            return pd.DataFrame(
                columns=["id", "date", "ticker", "signal", "entry_price", "volume", "capital_at_risk", "created_at"]
            )

        return df
    except Exception:
        logger.exception("Error loading trades")
        return pd.DataFrame()


def delete_trade(trade_id):
    """Delete a trade record by ID."""
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM trades WHERE id = :trade_id"), {"trade_id": int(trade_id)})
            _log_audit(conn, action="trade_deleted", trade_id=int(trade_id), details="manual delete")
        return True
    except Exception:
        logger.exception("Error deleting trade")
        return False


def get_trade_count():
    """Return the total number of trades in the database."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM trades"))
            return int(result.scalar() or 0)
    except Exception:
        logger.exception("Error getting trade count")
        return 0


def export_trades_csv(filename="trades_export.csv"):
    """Export all trades to a CSV file."""
    try:
        df = load_trades()
        output_path = Path(__file__).parent / filename
        df.to_csv(output_path, index=False)
        return str(output_path)
    except Exception:
        logger.exception("Error exporting trades")
        return None
