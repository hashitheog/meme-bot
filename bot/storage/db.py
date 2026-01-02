import sqlite3
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot/storage/cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS seen_pairs (
                    pair_address TEXT PRIMARY KEY,
                    chain_id TEXT,
                    seen_at TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY,
                    balance REAL DEFAULT 100.0,
                    realized_pnl REAL DEFAULT 0.0,
                    fees_paid REAL DEFAULT 0.0,
                    last_updated TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    token_address TEXT PRIMARY KEY,
                    symbol TEXT,
                    chain_id TEXT,
                    entry_price REAL,
                    current_quantity REAL,
                    cost_basis REAL,
                    last_tp_price REAL,
                    current_price REAL DEFAULT 0,
                    status TEXT,
                    log TEXT,
                    entry_time TIMESTAMP
                )
            ''')
            # Initialize portfolio if empty
            cursor.execute("INSERT OR IGNORE INTO portfolio (id, balance) VALUES (1, 200.0)")
            
            # --- MIGRATION: Check for current_price ---
            cursor.execute("PRAGMA table_info(trades)")
            columns = [info[1] for info in cursor.fetchall()]
            if "current_price" not in columns:
                logger.info("Migrating DB: Adding 'current_price' to trades table...")
                cursor.execute("ALTER TABLE trades ADD COLUMN current_price REAL DEFAULT 0")
            
            # --- Message Log Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_log (
                    message_id INTEGER PRIMARY KEY,
                    chat_id INTEGER,
                    timestamp TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database init failed: {e}")

    def is_seen(self, pair_address: str) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_pairs WHERE pair_address = ?", (pair_address,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception:
            return False

    def mark_seen(self, pair_address: str, chain_id: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO seen_pairs (pair_address, chain_id, seen_at) VALUES (?, ?, ?)",
                (pair_address, chain_id, datetime.now())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to mark pair as seen: {e}")
    def reset_data(self):
        """
        Clears the 'seen_pairs' table to restart scanning history.
        Also clears message log? No, we need IDs to delete first.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM seen_pairs")
            conn.commit()
            conn.close()
            logger.info("Database: Seen pairs cleared.")
        except Exception as e:
            logger.error(f"Failed to reset database: {e}")

    def log_message(self, chat_id, message_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO message_log (message_id, chat_id, timestamp) VALUES (?, ?, ?)", 
                           (message_id, chat_id, datetime.now()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log message: {e}")

    def get_and_clear_message_ids(self):
        ids = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id, message_id FROM message_log")
            ids = cursor.fetchall()
            
            # Clear table
            cursor.execute("DELETE FROM message_log")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch message logs: {e}")
        return ids
