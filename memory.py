import os
import sqlite3
from threading import Lock

# Use an absolute path to avoid ambiguity when the working directory changes
DB = os.path.abspath("memory.db")

# A process‑wide lock to serialize writes and avoid “database is locked” errors
_db_lock = Lock()


def _get_connection():
    """
    Centralised connection factory.
    * `timeout` gives SQLite a chance to wait for locks to clear.
    * `detect_types=sqlite3.PARSE_DECLTYPES` enables proper handling of
      DATE/DATETIME types if they are ever used.
    * `check_same_thread=False` allows the same connection object to be used
      from different threads (we still protect writes with a lock).
    """
    return sqlite3.connect(
        DB,
        timeout=30.0,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
    )


def init_db():
    """Create the required tables if they do not already exist."""
    with _db_lock, _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                ai TEXT NOT NULL,
                score REAL NOT NULL CHECK (score >= 0 AND score <= 1),
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evolution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                old_prompt TEXT NOT NULL,
                new_prompt TEXT NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def save_exchange(user: str, ai: str, score: float):
    """
    Store a single exchange.
    The function validates that `score` is a float in the [0, 1] range.
    """
    if not isinstance(score, (int, float)):
        raise ValueError("Score must be a numeric type.")
    if not (0.0 <= score <= 1.0):
        raise ValueError("Score must be between 0 and 1 inclusive.")

    with _db_lock, _get_connection() as conn:
        conn.execute(
            "INSERT INTO exchanges (user, ai, score) VALUES (?, ?, ?)",
            (user, ai, float(score)),
        )
        conn.commit()


def get_recent(n: int = 10):
    """Return the *n* most recent exchanges in chronological order (oldest → newest)."""
    with _get_connection() as conn:
        rows = (
            conn.execute(
                "SELECT user, ai, score FROM exchanges ORDER BY timestamp DESC LIMIT ?",
                (n,),
            )
            .fetchall()
        )
    # Reverse so the caller sees them from oldest to newest
    return [{"user": r[0], "ai": r[1], "score": r[2]} for r in reversed(rows)]


def get_low_scoring(threshold: float = 0.6):
    """Return up to 20 exchanges with a score below *threshold*."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT user, ai, score
            FROM exchanges
            WHERE score < ?
            ORDER BY timestamp DESC
            LIMIT 20
            """,
            (threshold,),
        ).fetchall()
    return [{"user": r[0], "ai": r[1], "score": r[2]} for r in rows]


def get_all_recent(n: int = 50):
    """Return the *n* most recent exchanges (newest → oldest)."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT user, ai, score FROM exchanges ORDER BY timestamp DESC LIMIT ?",
            (n,),
        ).fetchall()
    return [{"user": r[0], "ai": r[1], "score": r[2]} for r in rows]


def log_evolution(old_prompt: str, new_prompt: str, reason: str | None = None):
    """Record a prompt‑evolution event."""
    with _db_lock, _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO evolution_log (old_prompt, new_prompt, reason)
            VALUES (?, ?, ?)
            """,
            (old_prompt, new_prompt, reason),
        )
        conn.commit()


def get_stats():
    """Return a small summary of stored data."""
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()[0]
        avg = conn.execute("SELECT AVG(score) FROM exchanges").fetchone()[0] or 0.0
        evolutions = conn.execute("SELECT COUNT(*) FROM evolution_log").fetchone()[0]
    return {"total": total, "avg_score": avg, "evolutions": evolutions}