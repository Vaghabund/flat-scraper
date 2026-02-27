"""SQLite database interface for flat-scraper-bot."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id VARCHAR(255),
    url VARCHAR(512) UNIQUE NOT NULL,
    address VARCHAR(512),
    rooms INTEGER,
    floor INTEGER,
    price DECIMAL(10,2),
    area VARCHAR(255),
    description TEXT,
    scraped_at DATETIME NOT NULL,
    notified_at DATETIME,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a database connection with :class:`sqlite3.Row` row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Create the database file and tables if they do not exist.

    Also creates any parent directories required for ``db_path``.

    Args:
        db_path: Filesystem path to the SQLite database file.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def add_listing(db_path: str, data: dict) -> int:
    """Insert or update a listing record atomically.

    Uses SQLite's ``ON CONFLICT`` UPSERT syntax so that ``created_at`` and
    ``notified_at`` are never overwritten on an existing row.  This avoids the
    race condition of a separate SELECT followed by INSERT OR REPLACE.

    Args:
        db_path: Path to the SQLite database.
        data: Dictionary with listing fields.

    Returns:
        The ``id`` of the inserted or updated row.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO listings
                (site_id, url, address, rooms, floor, price, area, description,
                 scraped_at, is_active, created_at, updated_at)
            VALUES
                (:site_id, :url, :address, :rooms, :floor, :price, :area, :description,
                 :scraped_at, :is_active, :now, :now)
            ON CONFLICT(url) DO UPDATE SET
                site_id     = excluded.site_id,
                address     = excluded.address,
                rooms       = excluded.rooms,
                floor       = excluded.floor,
                price       = excluded.price,
                area        = excluded.area,
                description = excluded.description,
                scraped_at  = excluded.scraped_at,
                is_active   = excluded.is_active,
                updated_at  = excluded.updated_at
            """,
            {
                "site_id": data.get("site_id"),
                "url": data["url"],
                "address": data.get("address"),
                "rooms": data.get("rooms"),
                "floor": data.get("floor"),
                "price": data.get("price"),
                "area": data.get("area"),
                "description": data.get("description"),
                "scraped_at": data.get("scraped_at", now),
                "is_active": data.get("is_active", 1),
                "now": now,
            },
        )
        conn.commit()
        return conn.execute(
            "SELECT id FROM listings WHERE url = ?", (data["url"],)
        ).fetchone()["id"]
    finally:
        conn.close()


def get_new_listings(db_path: str, since_hours: int = 24) -> list[dict]:
    """Return listings scraped within the last ``since_hours`` that have not been notified.

    Args:
        db_path: Path to the SQLite database.
        since_hours: Look-back window in hours.

    Returns:
        List of listing dicts.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM listings WHERE scraped_at > ? AND notified_at IS NULL",
            (cutoff,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def mark_notified(db_path: str, listing_id: int) -> None:
    """Set ``notified_at`` to the current UTC time for a listing.

    Args:
        db_path: Path to the SQLite database.
        listing_id: Primary key of the listing to update.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE listings SET notified_at = ? WHERE id = ?", (now, listing_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_listing_by_url(db_path: str, url: str) -> dict | None:
    """Retrieve a single listing by its URL.

    Args:
        db_path: Path to the SQLite database.
        url: Unique URL of the listing.

    Returns:
        Listing dict, or ``None`` if not found.
    """
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM listings WHERE url = ?", (url,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def is_duplicate(db_path: str, url: str) -> bool:
    """Check whether a listing URL already exists in the database.

    Args:
        db_path: Path to the SQLite database.
        url: URL to check.

    Returns:
        ``True`` if the URL is already stored, ``False`` otherwise.
    """
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM listings WHERE url = ?", (url,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_recent_listings(db_path: str, limit: int = 5) -> list[dict]:
    """Return the most recently scraped listings.

    Args:
        db_path: Path to the SQLite database.
        limit: Maximum number of listings to return.

    Returns:
        List of listing dicts ordered by ``scraped_at`` descending.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM listings ORDER BY scraped_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
