"""Write stock movements and read current levels. Dev A owns this file."""
from .. import db
from .units import to_canonical


def apply_movement(shop_id, sku, direction, qty, unit, cost_rupees=None, source="chat"):
    """Record one stock in/out. Returns the action dict the API contract expects."""
    qty_canon, confident = to_canonical(qty, unit, sku["canonical_unit"], sku["name"])
    signed = qty_canon if direction == "in" else -qty_canon
    cost_paise = int(round(cost_rupees * 100)) if cost_rupees is not None else None

    db.execute(
        """INSERT INTO stock_ledger
           (shop_id, sku_id, direction, qty_canonical, raw_qty, raw_unit,
            cost_per_unit, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (shop_id, sku["id"], direction, qty_canon, qty, unit, cost_paise, source),
    )
    db.execute("UPDATE skus SET current_qty = current_qty + ? WHERE id = ?",
               (signed, sku["id"]))
    if cost_paise is not None:
        db.execute("UPDATE skus SET cost_per_unit = ? WHERE id = ?",
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
