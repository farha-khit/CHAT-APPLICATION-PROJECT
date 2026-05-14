"""
=============================================================================
DatabaseManager — SQLite persistence layer
=============================================================================
Handles:
  • User registration & login (passwords hashed with bcrypt)
  • Chat room tracking
  • Message history storage & retrieval
  • Message search
  • Read-receipt tracking

The database file is created automatically in  chat_app/database/chat.db
=============================================================================
"""

import sqlite3
import os
import threading
import bcrypt
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat.db")


class DatabaseManager:
    """Thread-safe SQLite wrapper for the chat application."""

    def __init__(self, db_path: str = DB_PATH):
        self._db_path = db_path
        self._local = threading.local()       # per-thread connection
        self._init_lock = threading.Lock()
        self._init_tables()

    # ------------------------------------------------------------------
    # Connection helper (one connection per thread)
    # ------------------------------------------------------------------
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------
    def _init_tables(self):
        with self._init_lock:
            conn = self._conn()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT    UNIQUE NOT NULL,
                    password    TEXT    NOT NULL,       -- bcrypt hash
                    created_at  TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rooms (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    UNIQUE NOT NULL,
                    created_at  TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT    NOT NULL,
                    room        TEXT    NOT NULL,
                    content     TEXT    NOT NULL,
                    timestamp   TEXT    NOT NULL,
                    is_read     INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS read_receipts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id  INTEGER NOT NULL,
                    reader      TEXT    NOT NULL,
                    read_at     TEXT    NOT NULL,
                    FOREIGN KEY (message_id) REFERENCES messages(id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_room
                    ON messages(room);
                CREATE INDEX IF NOT EXISTS idx_messages_ts
                    ON messages(timestamp);
            """)
            # Ensure the default room exists
            self.ensure_room("General")

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def register_user(self, username: str, password: str) -> tuple[bool, str]:
        """
        Register a new user.
        Returns (True, "success msg") or (False, "error msg").
        """
        conn = self._conn()
        try:
            # Hash the password with bcrypt
            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            conn.execute(
                "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
                (username, hashed.decode("utf-8"), _now()),
            )
            conn.commit()
            return True, f"User '{username}' registered successfully."
        except sqlite3.IntegrityError:
            return False, f"Username '{username}' is already taken."

    def verify_user(self, username: str, password: str) -> tuple[bool, str]:
        """
        Verify credentials.
        Returns (True, "ok") or (False, "error msg").
        """
        conn = self._conn()
        row = conn.execute(
            "SELECT password FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            return False, "User not found. Please register first."
        stored_hash = row["password"].encode("utf-8")
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return True, "Login successful."
        return False, "Incorrect password."

    # ------------------------------------------------------------------
    # Room management
    # ------------------------------------------------------------------

    def ensure_room(self, name: str):
        """Create the room row if it doesn't already exist."""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO rooms (name, created_at) VALUES (?, ?)",
                (name, _now()),
            )
            conn.commit()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Message persistence
    # ------------------------------------------------------------------

    def save_message(self, username: str, room: str, content: str, timestamp: str) -> int:
        """Insert a message and return its row id."""
        conn = self._conn()
        cur = conn.execute(
            "INSERT INTO messages (username, room, content, timestamp) VALUES (?, ?, ?, ?)",
            (username, room, content, timestamp),
        )
        conn.commit()
        return cur.lastrowid

    def get_history(self, room: str, limit: int = 50) -> list[dict]:
        """Return the last *limit* messages from *room*, oldest first."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT id, username, content, timestamp FROM messages "
            "WHERE room = ? ORDER BY id DESC LIMIT ?",
            (room, limit),
        ).fetchall()
        return [
            {"id": r["id"], "username": r["username"], "text": r["content"], "timestamp": r["timestamp"]}
            for r in reversed(rows)
        ]

    def search_messages(self, room: str, query: str, limit: int = 30) -> list[dict]:
        """Full-text search on messages in a room."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT id, username, content, timestamp FROM messages "
            "WHERE room = ? AND content LIKE ? ORDER BY id DESC LIMIT ?",
            (room, f"%{query}%", limit),
        ).fetchall()
        return [
            {"id": r["id"], "username": r["username"], "text": r["content"], "timestamp": r["timestamp"]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Read receipts
    # ------------------------------------------------------------------

    def mark_read(self, message_id: int, reader: str):
        conn = self._conn()
        conn.execute(
            "INSERT INTO read_receipts (message_id, reader, read_at) VALUES (?, ?, ?)",
            (message_id, reader, _now()),
        )
        conn.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
        conn.commit()


# ===========================================================================
# Helpers
# ===========================================================================
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
