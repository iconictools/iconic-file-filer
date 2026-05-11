"""Undo / action history backed by SQLite for Iconic File Filer."""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import time

from iconic_filer.constants import DEFAULT_HISTORY_DB, HISTORY_MAX_ACTIONS

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL    NOT NULL,
    src_path    TEXT    NOT NULL,
    dst_path    TEXT    NOT NULL,
    undone      INTEGER NOT NULL DEFAULT 0
);
"""


class History:
    """Records file-move actions and supports undo."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or DEFAULT_HISTORY_DB
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn: sqlite3.Connection = sqlite3.connect(
            self.db_path, check_same_thread=False
        )
        self._closed = False
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        try:
            self._conn.execute("ALTER TABLE actions ADD COLUMN source_folder TEXT")
            self._conn.commit()
            logger.debug("Migrated history DB: added source_folder column")
        except sqlite3.OperationalError as exc:
            if "duplicate column" in str(exc).lower():
                logger.debug("History DB: source_folder column already exists")
            else:
                logger.warning("History DB migration issue: %s", exc)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, src_path: str, dst_path: str, source_folder: str | None = None) -> int:
        """Record a file move and return the action id."""
        cur = self._conn.execute(
            "INSERT INTO actions (timestamp, src_path, dst_path, source_folder) VALUES (?, ?, ?, ?)",
            (time.time(), src_path, dst_path, source_folder),
        )
        self._conn.commit()
        self._prune()
        return cur.lastrowid  # type: ignore[return-value]

    def _prune(self) -> None:
        """Delete oldest rows when the table exceeds HISTORY_MAX_ACTIONS."""
        self._conn.execute(
            "DELETE FROM actions "
            "WHERE id < ("
            "    SELECT id FROM actions ORDER BY id DESC LIMIT 1 OFFSET ?"
            ")",
            (HISTORY_MAX_ACTIONS - 1,),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def undo_last(self) -> tuple[str, str] | None:
        """Undo the most recent non-undone action.

        Moves the file back and returns ``(dst_path, src_path)`` on success,
        or *None* if nothing to undo.
        """
        row = self._conn.execute(
            "SELECT id, src_path, dst_path FROM actions "
            "WHERE undone = 0 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None

        action_id, src_path, dst_path = row
        if not os.path.exists(dst_path):
            logger.warning("Undo skipped; destination no longer exists: %s", dst_path)
            return None
        try:
            os.makedirs(os.path.dirname(src_path) or ".", exist_ok=True)
            shutil.move(dst_path, src_path)
        except (OSError, shutil.Error) as exc:
            logger.error("Undo failed for %s -> %s: %s", dst_path, src_path, exc)
            return None

        self._conn.execute(
            "UPDATE actions SET undone = 1 WHERE id = ?", (action_id,)
        )
        self._conn.commit()
        return dst_path, src_path

    def undo_by_id(self, action_id: int) -> tuple[str, str] | None:
        """Undo a specific action by its *action_id*.

        Returns ``(dst_path, src_path)`` on success, or *None*.
        """
        row = self._conn.execute(
            "SELECT src_path, dst_path, undone FROM actions WHERE id = ?",
            (action_id,),
        ).fetchone()
        if row is None or row[2]:
            return None

        src_path, dst_path = row[0], row[1]
        if not os.path.exists(dst_path):
            logger.warning(
                "Undo by id skipped; destination no longer exists: %s (id=%s)",
                dst_path,
                action_id,
            )
            return None
        try:
            os.makedirs(os.path.dirname(src_path) or ".", exist_ok=True)
            shutil.move(dst_path, src_path)
        except (OSError, shutil.Error) as exc:
            logger.error(
                "Undo by id failed for %s -> %s (id=%s): %s",
                dst_path,
                src_path,
                action_id,
                exc,
            )
            return None

        self._conn.execute(
            "UPDATE actions SET undone = 1 WHERE id = ?", (action_id,)
        )
        self._conn.commit()
        return dst_path, src_path

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def recent(self, limit: int = 20) -> list[dict]:
        """Return the *limit* most recent actions."""
        rows = self._conn.execute(
            "SELECT id, timestamp, src_path, dst_path, undone "
            "FROM actions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "src_path": r[2],
                "dst_path": r[3],
                "undone": bool(r[4]),
            }
            for r in rows
        ]

    def pending_count(self) -> int:
        """Return the number of recorded but not-yet-undone actions."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM actions WHERE undone = 0"
        ).fetchone()
        return row[0] if row else 0

    def total_count(self) -> int:
        """Return the total number of actions ever recorded."""
        row = self._conn.execute("SELECT COUNT(*) FROM actions").fetchone()
        return row[0] if row else 0

    def count_since(self, since_timestamp: float) -> int:
        """Return the number of actions recorded after *since_timestamp*."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM actions WHERE timestamp >= ?",
            (since_timestamp,),
        ).fetchone()
        return row[0] if row else 0

    def clear_records(self) -> None:
        """Delete all history records without moving any files."""
        self._conn.execute("DELETE FROM actions")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public query helpers (avoid exposing _conn to callers)
    # ------------------------------------------------------------------

    def last_dest_for_ext(self, ext: str) -> str | None:
        """Return the most recent destination *directory* for files with *ext*.

        *ext* should include the dot, e.g. ``".pdf"``.  Returns *None* if
        there is no matching non-undone record.
        """
        ext_lower = ext.lower()
        row = self._conn.execute(
            "SELECT dst_path FROM actions WHERE undone=0 "
            "AND LOWER(src_path) LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%{ext_lower}",),
        ).fetchone()
        return os.path.dirname(row[0]) if row else None

    def all_timestamps(self) -> list[float]:
        """Return timestamps of all non-undone actions, newest first."""
        rows = self._conn.execute(
            "SELECT timestamp FROM actions WHERE undone=0 ORDER BY id DESC"
        ).fetchall()
        return [r[0] for r in rows]

    def all_src_paths(self) -> list[str]:
        """Return src_path of all non-undone actions."""
        rows = self._conn.execute(
            "SELECT src_path FROM actions WHERE undone=0"
        ).fetchall()
        return [r[0] for r in rows]

    def all_dst_paths(self) -> list[str]:
        """Return dst_path of all non-undone actions."""
        rows = self._conn.execute(
            "SELECT dst_path FROM actions WHERE undone=0"
        ).fetchall()
        return [r[0] for r in rows]

    def all_moves(self) -> list[tuple[str, str]]:
        """Return ``(src_path, dst_path)`` for all non-undone actions."""
        rows = self._conn.execute(
            "SELECT src_path, dst_path FROM actions WHERE undone=0"
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._conn.close()
