import sqlite3

DB = "memory.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            ai TEXT,
            score REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evolution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            old_prompt TEXT,
            new_prompt TEXT,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_exchange(user, ai, score):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO exchanges (user, ai, score) VALUES (?, ?, ?)", (user, ai, score))
    conn.commit()
    conn.close()

def get_recent(n=10):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT user, ai, score FROM exchanges ORDER BY timestamp DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [{"user": r[0], "ai": r[1], "score": r[2]} for r in reversed(rows)]

def get_low_scoring(threshold=0.6):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT user, ai, score FROM exchanges WHERE score < ? ORDER BY timestamp DESC LIMIT 20",
        (threshold,)
    ).fetchall()
    conn.close()
    return [{"user": r[0], "ai": r[1], "score": r[2]} for r in rows]

def get_all_recent(n=50):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT user, ai, score FROM exchanges ORDER BY timestamp DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [{"user": r[0], "ai": r[1], "score": r[2]} for r in rows]

def log_evolution(old_prompt, new_prompt, reason):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO evolution_log (old_prompt, new_prompt, reason) VALUES (?, ?, ?)",
        (old_prompt, new_prompt, reason)
    )
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB)
    total = conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()[0]
    avg = conn.execute("SELECT AVG(score) FROM exchanges").fetchone()[0] or 0
    evolutions = conn.execute("SELECT COUNT(*) FROM evolution_log").fetchone()[0]
    conn.close()
    return {"total": total, "avg_score": avg, "evolutions": evolutions}
