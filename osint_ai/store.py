"""SQLite-backed persistence for ingested articles and extracted entities."""
import sqlite3
from contextlib import contextmanager

from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    published_at TEXT,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT NOT NULL,
    text TEXT NOT NULL,
    label TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles (id)
);

CREATE INDEX IF NOT EXISTS idx_entities_article_id ON entities (article_id);

CREATE TABLE IF NOT EXISTS geocode_cache (
    place TEXT PRIMARY KEY,
    lat REAL,
    lon REAL,
    resolved INTEGER NOT NULL
);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _ensure_articles_sentiment_column(conn: sqlite3.Connection) -> None:
    """Add the sentiment column if this DB was created before M3 (SQLite has no ADD COLUMN IF NOT EXISTS)."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(articles)")}
    if "sentiment" not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN sentiment REAL")


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
        _ensure_articles_sentiment_column(conn)
        conn.commit()


def save_articles(articles: list[dict]) -> int:
    """Insert new articles, skipping ones already stored (by id). Returns count inserted."""
    if not articles:
        return 0
    with get_connection() as conn:
        cursor = conn.executemany(
            """
            INSERT OR IGNORE INTO articles (id, title, link, summary, source, published_at, fetched_at)
            VALUES (:id, :title, :link, :summary, :source, :published_at, :fetched_at)
            """,
            articles,
        )
        conn.commit()
        return cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0


def get_articles(limit: int | None = None) -> list[dict]:
    query = "SELECT * FROM articles ORDER BY published_at DESC"
    if limit:
        query += f" LIMIT {int(limit)}"
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]


def save_entities(article_id: str, entities: list[tuple[str, str]]) -> None:
    """Replace stored entities for one article with a fresh list of (text, label) pairs."""
    with get_connection() as conn:
        conn.execute("DELETE FROM entities WHERE article_id = ?", (article_id,))
        conn.executemany(
            "INSERT INTO entities (article_id, text, label) VALUES (?, ?, ?)",
            [(article_id, text, label) for text, label in entities],
        )
        conn.commit()


def get_entities(article_ids: list[str] | None = None) -> list[dict]:
    with get_connection() as conn:
        if article_ids:
            placeholders = ",".join("?" * len(article_ids))
            rows = conn.execute(
                f"SELECT * FROM entities WHERE article_id IN ({placeholders})",
                article_ids,
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM entities").fetchall()
        return [dict(row) for row in rows]


def has_entities(article_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM entities WHERE article_id = ? LIMIT 1", (article_id,)
        ).fetchone()
        return row is not None


def save_sentiment(article_id: str, score: float) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE articles SET sentiment = ? WHERE id = ?", (score, article_id)
        )
        conn.commit()


def get_articles_without_sentiment() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM articles WHERE sentiment IS NULL").fetchall()
        return [dict(row) for row in rows]


def get_place_mention_counts() -> list[dict]:
    """Distinct place entities (GPE/LOC) with how many articles mention each."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT text, COUNT(DISTINCT article_id) AS mentions
            FROM entities
            WHERE label IN ('GPE', 'LOC')
            GROUP BY text
            ORDER BY mentions DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_geocode(place: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM geocode_cache WHERE place = ?", (place,)
        ).fetchone()
        return dict(row) if row else None


def save_geocode(place: str, lat: float | None, lon: float | None, resolved: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO geocode_cache (place, lat, lon, resolved)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (place) DO UPDATE SET lat = excluded.lat, lon = excluded.lon,
                resolved = excluded.resolved
            """,
            (place, lat, lon, int(resolved)),
        )
        conn.commit()


def get_resolved_geocodes() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM geocode_cache WHERE resolved = 1"
        ).fetchall()
        return [dict(row) for row in rows]
