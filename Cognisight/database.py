# focus_sentry/database.py
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "focus_sentry.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            email TEXT,
            phone TEXT,
            alert_threshold_ms INTEGER NOT NULL,
            alert_mode TEXT NOT NULL,
            send_email INTEGER NOT NULL,
            send_sms INTEGER NOT NULL,
            ended_at TEXT,
            total_seconds INTEGER,
            focused_seconds INTEGER,
            unfocused_seconds INTEGER,
            breaks_count INTEGER,
            focus_percent INTEGER,
            ended_early INTEGER
        )
        """)
    conn.commit()
    conn.close()


def create_session(
    duration_minutes: int,
    email: Optional[str],
    phone: Optional[str],
    alert_threshold_ms: int,
    alert_mode: str,
    send_email: bool,
    send_sms: bool,
) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO focus_sessions (
            created_at,
            duration_minutes,
            email,
            phone,
            alert_threshold_ms,
            alert_mode,
            send_email,
            send_sms
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            duration_minutes,
            email,
            phone,
            alert_threshold_ms,
            alert_mode,
            1 if send_email else 0,
            1 if send_sms else 0,
        ),
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id


def complete_session(
    session_id: int,
    total_seconds: int,
    focused_seconds: int,
    unfocused_seconds: int,
    breaks_count: int,
    focus_percent: int,
    ended_early: bool,
):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE focus_sessions
        SET ended_at = ?,
            total_seconds = ?,
            focused_seconds = ?,
            unfocused_seconds = ?,
            breaks_count = ?,
            focus_percent = ?,
            ended_early = ?
        WHERE id = ?
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            total_seconds,
            focused_seconds,
            unfocused_seconds,
            breaks_count,
            focus_percent,
            1 if ended_early else 0,
            session_id,
        ),
    )
    conn.commit()

    cur.execute("SELECT * FROM focus_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_recent_sessions(limit: int = 20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM focus_sessions
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows
