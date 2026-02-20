"""
Database Module: SQLite Trade History Persistence

Handles all database operations for the Trading Assistant.
Stores trade records in a local SQLite database for persistence across sessions.
"""

import sqlite3
import pandas as pd
from pathlib import Path

# Database file location
DB_PATH = Path(__file__).parent / "trades.db"

def init_db():
    """Initialize the SQLite database and trades table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
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
    """)
    
    conn.commit()
    conn.close()
    print("✓ Database initialized successfully")

def save_trade(date, ticker, signal, entry_price, volume, capital_at_risk):
    """Insert a trade record into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO trades (date, ticker, signal, entry_price, volume, capital_at_risk)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (date, ticker.upper(), signal, entry_price, volume, capital_at_risk))
        
        conn.commit()
        trade_id = cursor.lastrowid
        return trade_id
    
    except Exception as e:
        print(f"Error saving trade: {e}")
        return None
    
    finally:
        conn.close()

def load_trades():
    """Query and return all trades with formatted prices."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY date DESC", conn)
        conn.close()
        
        if df.empty:
            return pd.DataFrame(columns=[
                'id', 'date', 'ticker', 'signal', 'entry_price', 'volume', 'capital_at_risk'
            ])
        
        # Format price and capital columns for display
        df['entry_price'] = df['entry_price'].apply(lambda x: f"${x:.2f}")
        df['capital_at_risk'] = df['capital_at_risk'].apply(lambda x: f"${x:.2f}")
        
        return df
    
    except Exception as e:
        print(f"Error loading trades: {e}")
        return pd.DataFrame()

def delete_trade(trade_id):
    """Delete a trade record by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        return True
    
    except Exception as e:
        print(f"Error deleting trade: {e}")
        return False
    
    finally:
        conn.close()

def get_trade_count():
    """Return the total number of trades in the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    except Exception as e:
        print(f"Error getting trade count: {e}")
        return 0

def export_trades_csv(filename="trades_export.csv"):
    """Export all trades to a CSV file."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY date DESC", conn)
        conn.close()
        
        output_path = Path(__file__).parent / filename
        df.to_csv(output_path, index=False)
        return str(output_path)
    
    except Exception as e:
        print(f"Error exporting trades: {e}")
        return None
