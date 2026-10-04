"""Create the demo shop: catalogue + 14 days of sales history.

Run:  python -m app.seed        (add --reset to wipe first)

The history is NOT optional. Without it, avg_daily_sales is 0, days-of-cover is
undefined, and the low-stock alert never fires. Seed before anything else.

Dev A owns this file.
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import db
from .config import log

CATALOG = Path(__file__).resolve().parent.parent / "data" / "catalog_seed.json"
SHOP_NAME = "Sharma Kirana Store"
SHOP_PHONE = "+919812345678"
HISTORY_DAYS = 14


def reset():
    with db.get_db() as conn:
        for t in ("pending_asks", "messages", "stock_ledger", "aliases", "skus", "shops"):
            conn.execute(f"DELETE FROM {t}")
        conn.execute("DELETE FROM sqlite_sequence")
    log("wiped")


def seed():
    db.init_db()

    existing = db.query_one("SELECT id FROM shops WHERE name = ?", (SHOP_NAME,))
    if existing:
        log(f"shop already seeded (id={existing['id']}). Use --reset to rebuild.")
        return existing["id"]

    shop_id = db.execute("INSERT INTO shops (name, owner_phone) VALUES (?, ?)",
                         (SHOP_NAME, SHOP_PHONE))
    items = json.loads(CATALOG.read_text(encoding="utf-8"))
    rng = random.Random(42)  # fixed seed -> the demo looks the same every run
    now = datetime.now(timezone.utc)

    for it in items:
        sku_id = db.execute(
            """INSERT INTO skus (shop_id, name, canonical_unit, current_qty,
                                 cost_per_unit, sell_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (shop_id, it["name"], it["unit"], it["qty"], it["cost"], it["sell"]),
        )

        for alias in it["aliases"]:
            db.execute(
                "INSERT OR IGNORE INTO aliases (shop_id, sku_id, alias_text) VALUES (?, ?, ?)",
                (shop_id, sku_id, alias.lower()),
            )

        # Daily sales with some jitter, so the numbers don't look synthetic.
        for d in range(HISTORY_DAYS, 0, -1):
            qty = round(it["daily"] * rng.uniform(0.55, 1.45), 1)
            if qty <= 0:
                continue
            ts = (now - timedelta(days=d, hours=rng.randint(0, 10))).isoformat(" ", "seconds")
            db.execute(
                """INSERT INTO stock_ledger (shop_id, sku_id, direction, qty_canonical,
                                             raw_qty, raw_unit, cost_per_unit, source, created_at)
                   VALUES (?, ?, 'out', ?, ?, ?, ?, 'seed', ?)""",
                (shop_id, sku_id, qty, qty, it["unit"], it["sell"], ts),
            )

        # A restock partway through, so the ledger isn't a one-way street.
        ts = (now - timedelta(days=rng.randint(4, 9))).isoformat(" ", "seconds")
        restock = round(it["daily"] * 10, 0) or 10
        db.execute(
            """INSERT INTO stock_ledger (shop_id, sku_id, direction, qty_canonical,
                                         raw_qty, raw_unit, cost_per_unit, source, created_at)
               VALUES (?, ?, 'in', ?, ?, ?, ?, 'seed', ?)""",
            (shop_id, sku_id, restock, restock, it["unit"], it["cost"], ts),
        )

    n_alias = db.query_one("SELECT COUNT(*) c FROM aliases WHERE shop_id = ?", (shop_id,))
    log(f"seeded shop {shop_id}: {len(items)} SKUs, {n_alias['c']} aliases, "
        f"{HISTORY_DAYS} days of history")

    from .core.reorder import alerts
    a = alerts(shop_id)
    log(f"{len(a)} items are already low -- the low-stock alert will have content")
    for x in a[:5]:
        log(f"   {x['name']}: {x['days_of_cover']} days left")
    return shop_id


if __name__ == "__main__":
    if "--reset" in sys.argv:
        db.init_db()
        reset()
    seed()
