"""Achievement system for Iconic File Filer."""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from iconic_filer.history import History

logger = logging.getLogger(__name__)


@dataclass
class Achievement:
    id: str
    name: str
    description: str
    emoji: str
    unlocked: bool = False
    unlocked_at: float = 0.0


_ALL_ACHIEVEMENTS = [
    Achievement("first_sort",     "First Sort",        "Sort your first file.",                        "🎉"),
    Achievement("ten_sorts",      "Sorting Spree",     "Sort 10 files.",                               "📦"),
    Achievement("hundred_sorts",  "Century Club",      "Sort 100 files.",                              "💯"),
    Achievement("thousand_sorts", "Sorting Machine",   "Sort 1,000 files.",                            "🤖"),
    Achievement("streak_3",       "3-Day Streak",      "Sort at least one file every day for 3 days.", "🔥"),
    Achievement("streak_7",       "Week Warrior",      "Sort at least one file every day for 7 days.", "⚡"),
    Achievement("streak_30",      "Month Master",      "Sort at least one file every day for 30 days.", "🏆"),
    Achievement("night_owl",      "Night Owl",         "Sort a file between midnight and 5 AM.",       "🦉"),
    Achievement("early_bird",     "Early Bird",        "Sort a file before 7 AM.",                     "🐦"),
    Achievement("speed_demon",    "Speed Demon",       "Sort 10 files in under 60 seconds.",           "💨"),
    Achievement("neat_freak",     "Neat Freak",        "Sort files into 5 different destinations.",    "✨"),
    Achievement("variety",        "Variety Pack",      "Sort 5 different file types.",                 "🎨"),
]


class Achievements:
    """Persists and evaluates achievements against the action history."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn: sqlite3.Connection = sqlite3.connect(
            db_path, check_same_thread=False
        )
        self._closed = False
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS achievements (
                id          TEXT PRIMARY KEY,
                unlocked_at REAL NOT NULL DEFAULT 0
            );
        """)

    def evaluate(self, history: "History") -> list[Achievement]:
        """Evaluate all achievements against *history*. Returns newly unlocked ones."""
        newly_unlocked: list[Achievement] = []
        already = {
            row[0] for row in
            self._conn.execute("SELECT id FROM achievements WHERE unlocked_at > 0").fetchall()
        }

        total = history.total_count()

        # Milestone counts
        for ach_id, threshold in [
            ("first_sort", 1), ("ten_sorts", 10),
            ("hundred_sorts", 100), ("thousand_sorts", 1000),
        ]:
            if ach_id not in already and total >= threshold:
                newly_unlocked.append(self._unlock(ach_id))

        # Streak: consecutive calendar days with at least one action
        timestamps = history.all_timestamps()
        days_with_activity: set[int] = {int(ts // 86400) for ts in timestamps}
        today = int(time.time() // 86400)
        for streak_len, ach_id in [(3, "streak_3"), (7, "streak_7"), (30, "streak_30")]:
            if ach_id not in already:
                consecutive = sum(
                    1 for i in range(streak_len)
                    if (today - i) in days_with_activity
                )
                if consecutive >= streak_len:
                    newly_unlocked.append(self._unlock(ach_id))

        # Night owl / early bird (local hour)
        for ts in timestamps:
            hour = time.localtime(ts).tm_hour
            if "night_owl" not in already and 0 <= hour < 5:
                newly_unlocked.append(self._unlock("night_owl"))
                already.add("night_owl")
            if "early_bird" not in already and 5 <= hour < 7:
                newly_unlocked.append(self._unlock("early_bird"))
                already.add("early_bird")
            if "night_owl" in already and "early_bird" in already:
                break

        # Speed demon: any sliding window of 10 consecutive sorts within 60 s
        if "speed_demon" not in already and len(timestamps) >= 10:
            ts_sorted = sorted(timestamps)
            for i in range(len(ts_sorted) - 9):
                if ts_sorted[i + 9] - ts_sorted[i] <= 60:
                    newly_unlocked.append(self._unlock("speed_demon"))
                    break

        # Neat freak: 5 distinct destination directories
        dst_paths = history.all_dst_paths()
        unique_dirs = {os.path.dirname(d) for d in dst_paths}
        if "neat_freak" not in already and len(unique_dirs) >= 5:
            newly_unlocked.append(self._unlock("neat_freak"))

        # Variety: 5 distinct file extensions
        src_paths = history.all_src_paths()
        exts = {os.path.splitext(s)[1].lower() for s in src_paths if os.path.splitext(s)[1]}
        if "variety" not in already and len(exts) >= 5:
            newly_unlocked.append(self._unlock("variety"))

        return newly_unlocked

    def _unlock(self, ach_id: str) -> Achievement:
        now = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO achievements (id, unlocked_at) VALUES (?, ?)",
            (ach_id, now),
        )
        self._conn.commit()
        ach = next((a for a in _ALL_ACHIEVEMENTS if a.id == ach_id), None)
        if ach is None:
            logger.warning("Unknown achievement id: %s", ach_id)
            return Achievement(ach_id, ach_id, "", "?", unlocked=True, unlocked_at=now)
        return Achievement(ach.id, ach.name, ach.description, ach.emoji,
                           unlocked=True, unlocked_at=now)

    def all_status(self) -> list[Achievement]:
        """Return all achievements with their unlock status."""
        unlocked_map = {
            row[0]: row[1]
            for row in self._conn.execute(
                "SELECT id, unlocked_at FROM achievements WHERE unlocked_at > 0"
            ).fetchall()
        }
        result = []
        for a in _ALL_ACHIEVEMENTS:
            unlocked = a.id in unlocked_map
            result.append(Achievement(
                a.id, a.name, a.description, a.emoji,
                unlocked=unlocked,
                unlocked_at=unlocked_map.get(a.id, 0.0),
            ))
        return result

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._conn.close()
