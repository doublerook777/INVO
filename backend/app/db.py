"""SQLite access. Stdlib only -- no ORM, no service to run.

Dev A owns this file.
"""
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH, log

SCHEMA = """
CREATE TABLE IF NOT EXISTS shops (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    owner_phone   TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skus (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id         INTEGER NOT NULL REFERENCES shops(id),
    name            TEXT NOT NULL,
    canonical_unit  TEXT NOT NULL,
    current_qty     REAL NOT NULL DEFAULT 0,
    cost_per_unit   INTEGER NOT NULL DEFAULT 0,   -- paise
    sell_price      INTEGER NOT NULL DEFAULT 0,   -- paise
    reorder_days    REAL NOT NULL DEFAULT 4,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- The learning table. Every time we ask the user "did you mean X?", the answer
-- lands here, and we never ask again. This is the product.
CREATE TABLE IF NOT EXISTS aliases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id     INTEGER NOT NULL REFERENCES shops(id),
    sku_id      INTEGER NOT NULL REFERENCES skus(id),
    alias_text  TEXT NOT NULL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(shop_id, alias_text)
);

CREATE TABLE IF NOT EXISTS stock_ledger (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id        INTEGER NOT NULL REFERENCES shops(id),
    sku_id         INTEGER NOT NULL REFERENCES skus(id),
    direction      TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    qty_canonical  REAL NOT NULL,     -- ALWAYS in the sku's canonical unit
    raw_qty        REAL,              -- what the user actually said
    raw_unit       TEXT,
    cost_per_unit  INTEGER,           -- paise
    source         TEXT DEFAULT 'chat',
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id     INTEGER NOT NULL REFERENCES shops(id),
    sender      TEXT NOT NULL,
    direction   TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    body        TEXT,
    media_type  TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Remembers that we asked a clarifying question, so the user's next message
-- can be read as the answer. One open ask per sender keeps this simple.
CREATE TABLE IF NOT EXISTS pending_asks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id         INTEGER NOT NULL,
    sender          TEXT NOT NULL,
    question        TEXT,
    candidates_json TEXT,
    raw_item_json   TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ledger_sku  ON stock_ledger(shop_id, sku_id);
CREATE INDEX IF NOT EXISTS idx_alias_text  ON aliases(shop_id, alias_text);
CREATE INDEX IF NOT EXISTS idx_pending     ON pending_asks(shop_id, sender);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
    log(f"schema ready at {DB_PATH}")


def query(sql, params=()):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid
