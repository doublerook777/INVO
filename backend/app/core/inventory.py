"""Write stock movements and read current levels. Dev A owns this file."""
from .. import db
from .units import GENERIC, normalize_unit, to_canonical


def create_sku(shop_id, name, unit=""):
    """Brand-new SKU, offered when the resolver couldn't match anything.

    The raw unit the owner used becomes the canonical unit, so the very first
    movement against it is always unit-confident (raw == canon) -- but only
    if it's actually a unit `units.py` understands. normalize_unit() passes
    an unrecognized word straight through unchanged, which used to let a junk
    unit become a SKU's canonical unit forever. Validate against GENERIC
    before trusting it.
    """
    normalized = normalize_unit(unit)
    canonical = normalized if normalized in GENERIC else "packet"
    sku_id = db.execute(
        "INSERT INTO skus (shop_id, name, canonical_unit) VALUES (?, ?, ?)",
        (shop_id, name.strip().title(), canonical),
    )
    return db.query_one("SELECT * FROM skus WHERE id = ?", (sku_id,))


def apply_movement(shop_id, sku, direction, qty, unit, cost_rupees=None, source="chat"):
    """Record one stock in/out, atomically. Returns the action dict the API
    contract expects.

    All three writes (ledger insert, qty update, optional cost update) share
    one connection and one commit -- db.execute() opens and commits its own
    connection per call, which means a crash between two of these three
    writes could leave the ledger and the SKU's current_qty out of sync.
    """
    qty_canon, confident = to_canonical(qty, unit, sku["canonical_unit"], sku["name"])
    signed = qty_canon if direction == "in" else -qty_canon

    cost_paise = None
    if cost_rupees is not None:
        # cost_rupees is the rate PER RAW UNIT as stated ("ek peti ka rate
        # 500 rupaye") -- cost_per_unit/sell_price must be priced per the
        # SKU's CANONICAL unit, using the exact same ratio as the quantity
        # conversion above. Without this, "500" got stored as-is even when
        # 1 peti = 24 packets, overstating the per-packet cost 24x.
        factor = (qty_canon / qty) if qty else 1.0
        per_canonical_rupees = (cost_rupees / factor) if factor else cost_rupees
        cost_paise = int(round(per_canonical_rupees * 100))

    with db.get_db() as conn:
        conn.execute(
            """INSERT INTO stock_ledger
               (shop_id, sku_id, direction, qty_canonical, raw_qty, raw_unit,
                cost_per_unit, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (shop_id, sku["id"], direction, qty_canon, qty, unit, cost_paise, source),
        )
        # Physical stock can't go negative -- a fat-fingered or over-eager
        # stock-out used to drive current_qty below zero with no guard.
        # The ledger still records the full movement as reported (an audit
        # trail should show what was actually said); only the running
        # balance is floored.
        row = conn.execute("SELECT current_qty FROM skus WHERE id = ?",
                            (sku["id"],)).fetchone()
        new_qty = max(0.0, row["current_qty"] + signed)
        conn.execute("UPDATE skus SET current_qty = ? WHERE id = ?",
                     (new_qty, sku["id"]))
        if cost_paise is not None:
            # A price means something different depending on direction: on
            # the way IN it's what the shop paid (cost_per_unit); on the way
            # OUT it's what the shop sold at (sell_price). Conflating the two
            # let a sale's price silently overwrite the buy cost.
            column = "cost_per_unit" if direction == "in" else "sell_price"
            conn.execute(f"UPDATE skus SET {column} = ? WHERE id = ?",
                         (cost_paise, sku["id"]))

    return {
        "type": f"stock_{direction}",
        "sku_id": sku["id"],
        "sku_name": sku["name"],
        "qty": qty,
        "unit": unit or sku["canonical_unit"],
        "qty_canonical": qty_canon,
        "cost_per_unit": cost_paise,
        "unit_confident": confident,
    }


def list_inventory(shop_id):
    """Current levels joined with sales velocity. Matches docs/api-contract.md."""
    from .reorder import days_of_cover, status_for

    skus = db.query("SELECT * FROM skus WHERE shop_id = ? ORDER BY name", (shop_id,))
    items = []
    for s in skus:
        avg, cover = days_of_cover(shop_id, s["id"], s["current_qty"])
        items.append({
            "sku_id": s["id"],
            "name": s["name"],
            "current_qty": round(s["current_qty"], 2),
            "unit": s["canonical_unit"],
            "cost_per_unit": s["cost_per_unit"],
            "sell_price": s["sell_price"],
            "avg_daily_sales": round(avg, 2),
            "days_of_cover": round(cover, 1) if cover is not None else None,
            "status": status_for(s["current_qty"], cover),
        })
    return items
