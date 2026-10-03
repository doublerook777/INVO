"""Messy item name -> a real SKU.

This is the hard part of the project and the thing that makes it more than a
chatbot wrapper. One shop says parle g / parle-g / chhota parle / पारले जी and
means the same box of biscuits.

Three tiers:
    exact alias       -> use it, say nothing
    fuzzy >= 85       -> use it, say nothing
    fuzzy 60..85      -> ASK ONCE, then write an alias row so we never ask again
    below 60          -> offer to create a new SKU

Dev A owns this file.
"""
from rapidfuzz import fuzz, process

from .. import db
from ..config import FUZZY_ASK_FLOOR, FUZZY_AUTO_ACCEPT, TIE_MARGIN

EXACT, FUZZY, ASK, NEW = "alias", "fuzzy", "ask", "new"


def _catalog(shop_id):
    return db.query("SELECT id, name, canonical_unit FROM skus WHERE shop_id = ?",
                    (shop_id,))


def _alias_hit(shop_id, text):
    return db.query_one(
        "SELECT sku_id FROM aliases WHERE shop_id = ? AND alias_text = ?",
        (shop_id, text.strip().lower()),
    )


def learn_alias(shop_id, sku_id, text):
    """The whole point. After this, the bot never asks about `text` again."""
    db.execute(
        "INSERT OR IGNORE INTO aliases (shop_id, sku_id, alias_text) VALUES (?, ?, ?)",
        (shop_id, sku_id, text.strip().lower()),
    )


def resolve(shop_id, raw_name):
    """Returns {'status': EXACT|FUZZY|ASK|NEW, 'sku': {...}|None, 'candidates': [...]}"""
    name = (raw_name or "").strip().lower()
    if not name:
        return {"status": NEW, "sku": None, "candidates": []}

    hit = _alias_hit(shop_id, name)
    if hit:
        sku = db.query_one("SELECT * FROM skus WHERE id = ?", (hit["sku_id"],))
        return {"status": EXACT, "sku": sku, "candidates": []}

    catalog = _catalog(shop_id)
    if not catalog:
        return {"status": NEW, "sku": None, "candidates": []}

    names = [c["name"].lower() for c in catalog]
    matches = process.extract(name, names, scorer=fuzz.WRatio, limit=3)

    if not matches:
        return {"status": NEW, "sku": None, "candidates": []}

    best_name, best_score, best_idx = matches[0]
    best = catalog[best_idx]

    # Near-tie: "amul" scores 90 against BOTH Amul Butter and Amul Taaza Milk.
    # Taking the first one silently writes stock against the wrong item, and
    # nobody notices until the numbers are wrong. Ask instead.
    if len(matches) > 1 and (best_score - matches[1][1]) <= TIE_MARGIN:
        tied = [catalog[i] for _, sc, i in matches if (best_score - sc) <= TIE_MARGIN]
        if len(tied) > 1:
            return {"status": ASK, "sku": None, "candidates": tied[:3]}

    if best_score >= FUZZY_AUTO_ACCEPT:
        learn_alias(shop_id, best["id"], name)
        return {"status": FUZZY, "sku": best, "candidates": []}

    if best_score >= FUZZY_ASK_FLOOR:
        candidates = [catalog[i] for _, _, i in matches]
        return {"status": ASK, "sku": None, "candidates": candidates}

    return {"status": NEW, "sku": None, "candidates": []}
