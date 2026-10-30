"""SQLite persistence for Luna's opt-ins, companion profile and game state."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any


UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


class Database:
    """A small per-operation SQLite wrapper.

    A new connection is used for each operation so the bot remains safe across
    Discord callbacks and task-loop iterations.  The schema is additive and
    can be created on top of the original Luna database without a migration
    step.
    """

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def initialize(self) -> None:
        with self.connect() as c:
            c.executescript(
                """
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

                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    nickname TEXT,
                    current_mood TEXT NOT NULL DEFAULT 'neutral',
                    mood_confidence REAL NOT NULL DEFAULT 0,
                    mood_updated_at TEXT,
                    friendship_score REAL NOT NULL DEFAULT 0,
                    affection_score REAL NOT NULL DEFAULT 0,
                    interaction_count INTEGER NOT NULL DEFAULT 0,
                    last_active_at TEXT,
                    last_active_date TEXT,
                    streak_days INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(user_id, guild_id)
                );

                CREATE TABLE IF NOT EXISTS relationship_daily (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    conversation_count INTEGER NOT NULL DEFAULT 0,
                    game_count INTEGER NOT NULL DEFAULT 0,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    friendship_points REAL NOT NULL DEFAULT 0,
                    affection_points REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY(user_id, guild_id, day)
                );

                CREATE TABLE IF NOT EXISTS voice_preferences (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    auto_reply INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(user_id, guild_id)
                );

                CREATE TABLE IF NOT EXISTS hotness_preferences (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    age_confirmed INTEGER NOT NULL DEFAULT 0,
                    jealous_enabled INTEGER NOT NULL DEFAULT 0,
                    boundary_mode TEXT NOT NULL DEFAULT 'normal',
                    updated_at TEXT,
                    PRIMARY KEY(user_id, guild_id)
                );

                CREATE INDEX IF NOT EXISTS idx_dm_log_user_time
                    ON dm_log(user_id, sent_at);
                CREATE INDEX IF NOT EXISTS idx_relationship_daily_day
                    ON relationship_daily(guild_id, day);
                """
            )

    # ------------------------------------------------------------------
    # Existing opt-in and channel settings
    # ------------------------------------------------------------------
    def set_optin(self, user_id: int, guild_id: int, enabled: bool) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO optins(user_id, guild_id, enabled) VALUES(?,?,?)
                ON CONFLICT(user_id,guild_id) DO UPDATE SET enabled=excluded.enabled""",
                (user_id, guild_id, int(enabled)),
            )

    def is_opted_in(self, user_id: int, guild_id: int) -> bool:
        with self.connect() as c:
            row = c.execute(
                "SELECT enabled FROM optins WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            ).fetchone()
            return bool(row and row["enabled"])

    def get_opted_in(self, guild_id: int) -> list[sqlite3.Row]:
        with self.connect() as c:
            return c.execute(
                "SELECT user_id FROM optins WHERE guild_id=? AND enabled=1", (guild_id,)
            ).fetchall()

    def set_channel(self, guild_id: int, channel_id: int) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO settings(guild_id, channel_id) VALUES(?,?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id""",
                (guild_id, channel_id),
            )

    def get_channel(self, guild_id: int) -> int | None:
        with self.connect() as c:
            row = c.execute(
                "SELECT channel_id FROM settings WHERE guild_id=?", (guild_id,)
            ).fetchone()
            return int(row["channel_id"]) if row and row["channel_id"] else None

    def set_channel_enabled(self, guild_id: int, enabled: bool) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO settings(guild_id, channel_enabled) VALUES(?,?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_enabled=excluded.channel_enabled""",
                (guild_id, int(enabled)),
            )

    def channel_enabled(self, guild_id: int) -> bool:
        with self.connect() as c:
            row = c.execute(
                "SELECT channel_enabled FROM settings WHERE guild_id=?", (guild_id,)
            ).fetchone()
            return bool(row and row["channel_enabled"])

    def dm_count_today(self, user_id: int) -> int:
        today = utc_now().date().isoformat()
        with self.connect() as c:
            return int(
                c.execute(
                    "SELECT COUNT(*) FROM dm_log WHERE user_id=? AND sent_at LIKE ?",
                    (user_id, today + "%"),
                ).fetchone()[0]
            )

    def log_dm(self, user_id: int) -> None:
        with self.connect() as c:
            c.execute(
                "INSERT INTO dm_log(user_id, sent_at) VALUES(?,?)",
                (user_id, utc_now().isoformat()),
            )

    # ------------------------------------------------------------------
    # Profile, mood and relationship progression
    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_profile(c: sqlite3.Connection, user_id: int, guild_id: int) -> None:
        c.execute(
            "INSERT OR IGNORE INTO profiles(user_id, guild_id) VALUES(?, ?)",
            (user_id, guild_id),
        )

    @staticmethod
    def _ensure_daily(c: sqlite3.Connection, user_id: int, guild_id: int, day: str) -> None:
        c.execute(
            "INSERT OR IGNORE INTO relationship_daily(user_id, guild_id, day) VALUES(?, ?, ?)",
            (user_id, guild_id, day),
        )

    def get_profile(self, user_id: int, guild_id: int) -> dict[str, Any] | None:
        with self.connect() as c:
            row = c.execute(
                "SELECT * FROM profiles WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            ).fetchone()
            return dict(row) if row else None

    def get_or_create_profile(self, user_id: int, guild_id: int) -> dict[str, Any]:
        with self.connect() as c:
            self._ensure_profile(c, user_id, guild_id)
            row = c.execute(
                "SELECT * FROM profiles WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            ).fetchone()
            return dict(row)

    def set_nickname(self, user_id: int, guild_id: int, nickname: str | None) -> None:
        with self.connect() as c:
            self._ensure_profile(c, user_id, guild_id)
            c.execute(
                "UPDATE profiles SET nickname=? WHERE user_id=? AND guild_id=?",
                (nickname, user_id, guild_id),
            )

    def get_nickname(self, user_id: int, guild_id: int) -> str | None:
        profile = self.get_profile(user_id, guild_id)
        return profile.get("nickname") if profile else None

    def _apply_relationship_event(
        self,
        c: sqlite3.Connection,
        user_id: int,
        guild_id: int,
        *,
        friendship_delta: float,
        affection_delta: float,
        daily_cap: int,
        event_type: str,
        mood: str | None = None,
        mood_confidence: float = 0.0,
    ) -> dict[str, Any]:
        now = utc_now()
        today = now.date()
        today_text = today.isoformat()
        self._ensure_profile(c, user_id, guild_id)
        self._ensure_daily(c, user_id, guild_id, today_text)

        profile = c.execute(
            "SELECT * FROM profiles WHERE user_id=? AND guild_id=?",
            (user_id, guild_id),
        ).fetchone()
        daily = c.execute(
            "SELECT * FROM relationship_daily WHERE user_id=? AND guild_id=? AND day=?",
            (user_id, guild_id, today_text),
        ).fetchone()

        # Points stop after the daily cap, while mood and activity metadata
        # still update.  This prevents a bot/game loop from manufacturing an
        # unlimited relationship score.
        can_earn = int(daily["event_count"]) < max(1, daily_cap)
        earned_friendship = float(friendship_delta) if can_earn else 0.0
        earned_affection = float(affection_delta) if can_earn else 0.0

        last_date = profile["last_active_date"]
        if last_date == today_text:
            streak = int(profile["streak_days"] or 0) or 1
        elif last_date == (today - timedelta(days=1)).isoformat():
            streak = int(profile["streak_days"] or 0) + 1
        else:
            streak = 1

        last_mood = mood or profile["current_mood"] or "neutral"
        last_confidence = float(mood_confidence or profile["mood_confidence"] or 0)
        new_friendship = min(100.0, max(0.0, float(profile["friendship_score"]) + earned_friendship))
        new_affection = min(100.0, max(0.0, float(profile["affection_score"]) + earned_affection))
        interactions = int(profile["interaction_count"] or 0) + (1 if event_type == "conversation" else 0)

        c.execute(
            """UPDATE profiles SET
                current_mood=?, mood_confidence=?, mood_updated_at=?,
                friendship_score=?, affection_score=?, interaction_count=?,
                last_active_at=?, last_active_date=?, streak_days=?
            WHERE user_id=? AND guild_id=?""",
            (
                last_mood,
                last_confidence,
                now.isoformat(),
                new_friendship,
                new_affection,
                interactions,
                now.isoformat(),
                today_text,
                streak,
                user_id,
                guild_id,
            ),
        )

        c.execute(
            f"""UPDATE relationship_daily SET
                {event_type}_count={event_type}_count + 1,
                event_count=event_count + 1,
                friendship_points=friendship_points + ?,
                affection_points=affection_points + ?
            WHERE user_id=? AND guild_id=? AND day=?""",
            (
                earned_friendship,
                earned_affection,
                user_id,
                guild_id,
                today_text,
            ),
        )
        updated = c.execute(
            "SELECT * FROM profiles WHERE user_id=? AND guild_id=?",
            (user_id, guild_id),
        ).fetchone()
        result = dict(updated)
        result["earned_friendship"] = earned_friendship
        result["earned_affection"] = earned_affection
        result["daily_capped"] = not can_earn
        return result

    def record_conversation(
        self,
        user_id: int,
        guild_id: int,
        *,
        mood: str,
        mood_confidence: float,
        friendship_delta: float,
        affection_delta: float,
        daily_cap: int = 40,
    ) -> dict[str, Any]:
        with self.connect() as c:
            return self._apply_relationship_event(
                c,
                user_id,
                guild_id,
                friendship_delta=friendship_delta,
                affection_delta=affection_delta,
                daily_cap=daily_cap,
                event_type="conversation",
                mood=mood,
                mood_confidence=mood_confidence,
            )

    def record_game(
        self,
        user_id: int,
        guild_id: int,
        *,
        friendship_delta: float,
        affection_delta: float,
        daily_cap: int = 40,
    ) -> dict[str, Any]:
        with self.connect() as c:
            return self._apply_relationship_event(
                c,
                user_id,
                guild_id,
                friendship_delta=friendship_delta,
                affection_delta=affection_delta,
                daily_cap=daily_cap,
                event_type="game",
            )

    def get_daily_stats(self, user_id: int, guild_id: int, day: date | None = None) -> dict[str, Any]:
        day_text = (day or utc_now().date()).isoformat()
        with self.connect() as c:
            row = c.execute(
                "SELECT * FROM relationship_daily WHERE user_id=? AND guild_id=? AND day=?",
                (user_id, guild_id, day_text),
            ).fetchone()
            if row:
                return dict(row)
        return {
            "user_id": user_id,
            "guild_id": guild_id,
            "day": day_text,
            "conversation_count": 0,
            "game_count": 0,
            "event_count": 0,
            "friendship_points": 0.0,
            "affection_points": 0.0,
        }

    def get_relationship(self, user_id: int, guild_id: int) -> dict[str, Any]:
        profile = self.get_or_create_profile(user_id, guild_id)
        profile["daily"] = self.get_daily_stats(user_id, guild_id)
        return profile

    # ------------------------------------------------------------------
    # Voice preferences and privacy
    # ------------------------------------------------------------------
    def set_voice_mode(self, user_id: int, guild_id: int, enabled: bool) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO voice_preferences(user_id, guild_id, auto_reply) VALUES(?,?,?)
                ON CONFLICT(user_id,guild_id) DO UPDATE SET auto_reply=excluded.auto_reply""",
                (user_id, guild_id, int(enabled)),
            )

    def voice_mode(self, user_id: int, guild_id: int) -> bool:
        with self.connect() as c:
            row = c.execute(
                "SELECT auto_reply FROM voice_preferences WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            ).fetchone()
            return bool(row and row["auto_reply"])

    # ------------------------------------------------------------------
    # Consent-gated mature-romance preferences
    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_hotness(c: sqlite3.Connection, user_id: int, guild_id: int) -> None:
        c.execute(
            "INSERT OR IGNORE INTO hotness_preferences(user_id, guild_id) VALUES(?, ?)",
            (user_id, guild_id),
        )

    def get_hotness(self, user_id: int, guild_id: int) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "user_id": user_id,
            "guild_id": guild_id,
            "enabled": 0,
            "level": 1,
            "age_confirmed": 0,
            "jealous_enabled": 0,
            "boundary_mode": "normal",
            "updated_at": None,
        }
        with self.connect() as c:
            row = c.execute(
                "SELECT * FROM hotness_preferences WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            ).fetchone()
            if row:
                defaults.update(dict(row))
        return defaults

    def set_age_confirmed(self, user_id: int, guild_id: int, confirmed: bool) -> None:
        with self.connect() as c:
            self._ensure_hotness(c, user_id, guild_id)
            c.execute(
                """UPDATE hotness_preferences SET age_confirmed=?, enabled=?,
                    boundary_mode=?, updated_at=?
                WHERE user_id=? AND guild_id=?""",
                (
                    int(confirmed),
                    0,
                    "normal" if confirmed else "stop",
                    utc_now().isoformat(),
                    user_id,
                    guild_id,
                ),
            )

    def set_hotness_enabled(self, user_id: int, guild_id: int, enabled: bool) -> None:
        with self.connect() as c:
            self._ensure_hotness(c, user_id, guild_id)
            c.execute(
                "UPDATE hotness_preferences SET enabled=?, updated_at=? WHERE user_id=? AND guild_id=?",
                (int(enabled), utc_now().isoformat(), user_id, guild_id),
            )

    def set_hotness_level(self, user_id: int, guild_id: int, level: int) -> None:
        with self.connect() as c:
            self._ensure_hotness(c, user_id, guild_id)
            c.execute(
                "UPDATE hotness_preferences SET level=?, updated_at=? WHERE user_id=? AND guild_id=?",
                (max(1, min(3, int(level))), utc_now().isoformat(), user_id, guild_id),
            )

    def set_jealous_mode(self, user_id: int, guild_id: int, enabled: bool) -> None:
        with self.connect() as c:
            self._ensure_hotness(c, user_id, guild_id)
            c.execute(
                "UPDATE hotness_preferences SET jealous_enabled=?, updated_at=? WHERE user_id=? AND guild_id=?",
                (int(enabled), utc_now().isoformat(), user_id, guild_id),
            )

    def set_hotness_boundary(self, user_id: int, guild_id: int, mode: str) -> None:
        mode = mode if mode in {"normal", "soft", "stop"} else "soft"
        with self.connect() as c:
            self._ensure_hotness(c, user_id, guild_id)
            c.execute(
                """UPDATE hotness_preferences SET boundary_mode=?, enabled=?, updated_at=?
                WHERE user_id=? AND guild_id=?""",
                (
                    mode,
                    0,
                    utc_now().isoformat(),
                    user_id,
                    guild_id,
                ),
            )

    def delete_user_data(self, user_id: int, guild_id: int | None = None) -> None:
        with self.connect() as c:
            if guild_id is None:
                c.execute("DELETE FROM optins WHERE user_id=?", (user_id,))
                c.execute("DELETE FROM profiles WHERE user_id=?", (user_id,))
                c.execute("DELETE FROM relationship_daily WHERE user_id=?", (user_id,))
                c.execute("DELETE FROM voice_preferences WHERE user_id=?", (user_id,))
                c.execute("DELETE FROM hotness_preferences WHERE user_id=?", (user_id,))
            else:
                c.execute("DELETE FROM optins WHERE user_id=? AND guild_id=?", (user_id, guild_id))
                c.execute("DELETE FROM profiles WHERE user_id=? AND guild_id=?", (user_id, guild_id))
                c.execute(
                    "DELETE FROM relationship_daily WHERE user_id=? AND guild_id=?",
                    (user_id, guild_id),
                )
                c.execute(
                    "DELETE FROM voice_preferences WHERE user_id=? AND guild_id=?",
                    (user_id, guild_id),
                )
                c.execute(
                    "DELETE FROM hotness_preferences WHERE user_id=? AND guild_id=?",
                    (user_id, guild_id),
                )
            c.execute("DELETE FROM dm_log WHERE user_id=?", (user_id,))
