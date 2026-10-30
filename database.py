import sqlite3
from pathlib import Path
from datetime import datetime, timezone

class Database:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def initialize(self):
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS optins (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(user_id, guild_id)
            );
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                channel_enabled INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS dm_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sent_at TEXT NOT NULL
            );
            """)

    def set_optin(self, user_id, guild_id, enabled):
        with self.connect() as c:
            c.execute("""INSERT INTO optins(user_id,guild_id,enabled) VALUES(?,?,?)
            ON CONFLICT(user_id,guild_id) DO UPDATE SET enabled=excluded.enabled""",
            (user_id, guild_id, int(enabled)))

    def is_opted_in(self, user_id, guild_id):
        with self.connect() as c:
            row = c.execute("SELECT enabled FROM optins WHERE user_id=? AND guild_id=?", (user_id,guild_id)).fetchone()
            return bool(row and row["enabled"])

    def get_opted_in(self, guild_id):
        with self.connect() as c:
            return c.execute("SELECT user_id FROM optins WHERE guild_id=? AND enabled=1", (guild_id,)).fetchall()

    def set_channel(self, guild_id, channel_id):
        with self.connect() as c:
            c.execute("""INSERT INTO settings(guild_id,channel_id) VALUES(?,?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id""", (guild_id, channel_id))

    def get_channel(self, guild_id):
        with self.connect() as c:
            row = c.execute("SELECT channel_id FROM settings WHERE guild_id=?", (guild_id,)).fetchone()
            return row["channel_id"] if row else None

    def set_channel_enabled(self, guild_id, enabled):
        with self.connect() as c:
            c.execute("""INSERT INTO settings(guild_id,channel_enabled) VALUES(?,?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_enabled=excluded.channel_enabled""", (guild_id, int(enabled)))

    def channel_enabled(self, guild_id):
        with self.connect() as c:
            row = c.execute("SELECT channel_enabled FROM settings WHERE guild_id=?", (guild_id,)).fetchone()
            return bool(row and row["channel_enabled"])

    def dm_count_today(self, user_id):
        today = datetime.now(timezone.utc).date().isoformat()
        with self.connect() as c:
            return c.execute("SELECT COUNT(*) FROM dm_log WHERE user_id=? AND sent_at LIKE ?",
                             (user_id, today + "%")).fetchone()[0]

    def log_dm(self, user_id):
        with self.connect() as c:
            c.execute("INSERT INTO dm_log(user_id,sent_at) VALUES(?,?)",
                      (user_id, datetime.now(timezone.utc).isoformat()))
