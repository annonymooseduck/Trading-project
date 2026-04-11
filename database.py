"""Database operations for trade persistence with Postgres-first configuration."""

import base64
import hashlib
import hmac
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "trades.db"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def _get_database_url():
    """Get DATABASE_URL from environment or Streamlit secrets."""
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
        raise RuntimeError("DATABASE_URL is required. Configure it in Streamlit secrets or environment variables.")

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return database_url


@lru_cache(maxsize=1)
def _get_engine():
    db_url = _normalize_database_url(_get_database_url())
    backend = "Postgres" if "postgresql" in db_url else "SQLite"
    logger.info("Using database backend: %s", backend)
    if backend != "Postgres":
        logger.warning("Non-Postgres backend configured. Use Postgres in production for cross-device data access.")
    if backend == "Postgres":
        return create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 8})
    return create_engine(db_url, pool_pre_ping=True)


def _log_audit(conn, action, user_id, trade_id=None, details=""):
    conn.execute(
        text(
            """
            INSERT INTO audit_log (action, user_id, trade_id, details)
            VALUES (:action, :user_id, :trade_id, :details)
            """
        ),
        {"action": action, "user_id": user_id, "trade_id": trade_id, "details": details},
    )


def _hash_password(password, salt=None):
    """Create a PBKDF2 password hash with salt."""
    if salt is None:
        salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return base64.b64encode(salt).decode("utf-8"), base64.b64encode(password_hash).decode("utf-8")


def _verify_password(password, salt_b64, expected_hash_b64):
    salt = base64.b64decode(salt_b64.encode("utf-8"))
    _, actual_hash_b64 = _hash_password(password, salt=salt)
    return hmac.compare_digest(actual_hash_b64, expected_hash_b64)


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
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(32) UNIQUE NOT NULL,
                            password_salt TEXT NOT NULL,
                            password_hash TEXT NOT NULL,
                            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS trades (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            trade_id INTEGER,
                            details TEXT,
                            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                # Add user_id columns for existing databases created before authentication support.
                conn.execute(text("ALTER TABLE trades ADD COLUMN IF NOT EXISTS user_id INTEGER"))
                conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_id INTEGER"))
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password_salt TEXT NOT NULL,
                            password_hash TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS trades (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
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
                            user_id INTEGER NOT NULL,
                            trade_id INTEGER,
                            details TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
    except Exception:
        logger.exception("Failed to initialize database")
        raise


def register_user(username, password):
    """Create a new user account and return (success, message)."""
    clean_username = (username or "").strip()
    if not USERNAME_PATTERN.fullmatch(clean_username):
        return False, "Username must be 3-32 characters and use letters, numbers, '.', '_' or '-'."

    if len(password or "") < 8:
        return False, "Password must be at least 8 characters."

    try:
        salt_b64, hash_b64 = _hash_password(password)
        engine = _get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO users (username, password_salt, password_hash)
                    VALUES (:username, :password_salt, :password_hash)
                    """
                ),
                {
                    "username": clean_username,
                    "password_salt": salt_b64,
                    "password_hash": hash_b64,
                },
            )
        return True, "Account created. You can now log in."
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            return False, "Username already exists."
        logger.exception("Error registering user")
        return False, "Registration failed. Please try again."


def authenticate_user(username, password):
    """Validate credentials and return user dict when successful."""
    clean_username = (username or "").strip()
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, username, password_salt, password_hash
                    FROM users
                    WHERE username = :username
                    """
                ),
                {"username": clean_username},
            ).mappings().first()

        if not row:
            return None

        if _verify_password(password or "", row["password_salt"], row["password_hash"]):
            return {"id": int(row["id"]), "username": row["username"]}

        return None
    except Exception:
        logger.exception("Error authenticating user")
        return None


def save_trade(date, ticker, signal, entry_price, volume, capital_at_risk, user_id):
    """Insert a trade record and return its ID."""
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            dialect = conn.engine.dialect.name
            if dialect == "postgresql":
                result = conn.execute(
                    text(
                        """
                        INSERT INTO trades (user_id, date, ticker, signal, entry_price, volume, capital_at_risk)
                        VALUES (:user_id, :date, :ticker, :signal, :entry_price, :volume, :capital_at_risk)
                        RETURNING id
                        """
                    ),
                    {
                        "user_id": int(user_id),
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
                        INSERT INTO trades (user_id, date, ticker, signal, entry_price, volume, capital_at_risk)
                        VALUES (:user_id, :date, :ticker, :signal, :entry_price, :volume, :capital_at_risk)
                        """
                    ),
                    {
                        "user_id": int(user_id),
                        "date": date,
                        "ticker": ticker.upper(),
                        "signal": signal,
                        "entry_price": float(entry_price),
                        "volume": float(volume),
                        "capital_at_risk": float(capital_at_risk),
                    },
                )
                trade_id = result.lastrowid

            _log_audit(
                conn,
                action="trade_saved",
                user_id=int(user_id),
                trade_id=trade_id,
                details=f"ticker={ticker.upper()},signal={signal}",
            )
            return trade_id
    except Exception:
        logger.exception("Error saving trade")
        return None


def load_trades(user_id):
    """Query and return all trades with raw numeric values."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            df = pd.read_sql_query(
                text("SELECT * FROM trades WHERE user_id = :user_id ORDER BY date DESC"),
                conn,
                params={"user_id": int(user_id)},
            )

        if df.empty:
            return pd.DataFrame(
                columns=["id", "date", "ticker", "signal", "entry_price", "volume", "capital_at_risk", "created_at"]
            )

        return df
    except Exception:
        logger.exception("Error loading trades")
        return pd.DataFrame()


def delete_trade(trade_id, user_id):
    """Delete a trade record by ID."""
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM trades WHERE id = :trade_id AND user_id = :user_id"),
                {"trade_id": int(trade_id), "user_id": int(user_id)},
            )
            _log_audit(
                conn,
                action="trade_deleted",
                user_id=int(user_id),
                trade_id=int(trade_id),
                details="manual delete",
            )
        return True
    except Exception:
        logger.exception("Error deleting trade")
        return False


def get_trade_count(user_id):
    """Return the total number of trades in the database."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM trades WHERE user_id = :user_id"),
                {"user_id": int(user_id)},
            )
            return int(result.scalar() or 0)
    except Exception:
        logger.exception("Error getting trade count")
        return 0


def export_trades_csv(filename="trades_export.csv", user_id=None):
    """Export all trades to a CSV file."""
    try:
        if user_id is None:
            raise ValueError("user_id is required for export")
        df = load_trades(user_id=user_id)
        output_path = Path(__file__).parent / filename
        df.to_csv(output_path, index=False)
        return str(output_path)
    except Exception:
        logger.exception("Error exporting trades")
        return None
