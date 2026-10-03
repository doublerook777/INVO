"""The orchestrator. Every message -- WhatsApp, web, curl -- comes through here.

This function knows nothing about WhatsApp. That's deliberate: if the Twilio
integration dies at hour 4, we lose a transport, not the product.

Dev A owns this file.
"""
import json

from .. import db
from ..config import log
from . import extract as extract_mod
from . import inventory, reply, resolver


def _log_message(shop_id, sender, direction, body, media_type=None):
    db.execute(
        """INSERT INTO messages (shop_id, sender, direction, body, media_type)
           VALUES (?, ?, ?, ?, ?)""",
        (shop_id, sender, direction, body, media_type),
    )


def _get_pending(shop_id, sender):
    return db.query_one(
        """SELECT * FROM pending_asks WHERE shop_id = ? AND sender = ?
           ORDER BY id DESC LIMIT 1""",
        (shop_id, sender),
    )


def _clear_pending(shop_id, sender):
    db.execute("DELETE FROM pending_asks WHERE shop_id = ? AND sender = ?",
               (shop_id, sender))


def _save_pending(shop_id, sender, question, candidates, raw_item):
    _clear_pending(shop_id, sender)
    db.execute(
        """INSERT INTO pending_asks
           (shop_id, sender, question, candidates_json, raw_item_json)
           VALUES (?, ?, ?, ?, ?)""",
        (shop_id, sender, question, json.dumps(candidates), json.dumps(raw_item)),
    )


# Free-text equivalents so WhatsApp users who type instead of tapping a
# button still work -- the sandbox has no tappable buttons, only the web UI
# options carry literal "new"/"cancel" values.
CANCEL_WORDS = {"cancel", "nahi", "no", "na"}
NEW_WORDS = {"new", "haan", "haan, add karo", "yes", "ha", "add karo"}


def _answer_pending(shop_id, sender, text, pending):
    """User just answered 'which item did you mean?'. Learn it, then apply."""
    raw_item = json.loads(pending["raw_item_json"])
    candidates = json.loads(pending["candidates_json"])
    choice = (text or "").strip().lower()
    _clear_pending(shop_id, sender)

    if choice in CANCEL_WORDS:
        return {"reply": reply.cancelled(), "actions": [], "needs_answer": False,
                "debug": {"matched_via": "cancelled"}}

    created = False
    sku = None
    if choice in NEW_WORDS:
        sku = inventory.create_sku(shop_id, raw_item["name"], raw_item.get("unit", ""))
        created = True
    elif choice.startswith("sku:"):
        sku = db.query_one("SELECT * FROM skus WHERE id = ?", (int(choice[4:]),))
    else:
        for c in candidates:
            if choice in c["name"].lower() or c["name"].lower().startswith(choice):
                sku = db.query_one("SELECT * FROM skus WHERE id = ?", (c["id"],))
                break

    if not sku:
        return {"reply": reply.not_understood(), "actions": [], "needs_answer": False}

    # The moment that matters: remember this mapping forever.
    resolver.learn_alias(shop_id, sku["id"], raw_item["name"])
    log(f"learned alias: '{raw_item['name']}' -> {sku['name']}")

    action = inventory.apply_movement(
        shop_id, sku, raw_item.get("direction", "in"),
        raw_item["qty"], raw_item.get("unit", ""), raw_item.get("price_rupees"),
    )
    if created:
        msg = f"{reply.created_new(sku['name'])}\n{reply.confirm([action])}"
    else:
        msg = reply.confirm([action]) + f"\nAb se '{raw_item['name']}' yaad rahega."
    return {
        "reply": msg,
        "actions": [action],
        "needs_answer": False,
        "debug": {"matched_via": "new_sku" if created else "user_answer",
                  "alias_learned": raw_item["name"]},
    }


def handle_message(shop_id, sender, text=None, transcript=None):
    """Main entry point. Returns the dict in docs/api-contract.md."""
    body = text or transcript or ""
    _log_message(shop_id, sender, "in", body)

    pending = _get_pending(shop_id, sender)
    if pending:
        result = _answer_pending(shop_id, sender, body, pending)
        result["transcript"] = transcript
        _log_message(shop_id, sender, "out", result["reply"])
        return result

    parsed = extract_mod.extract(body)
    direction = "out" if parsed["intent"] == "stock_out" else "in"

    actions, out = [], None
    for item in parsed.get("items", []):
        res = resolver.resolve(shop_id, item["name"])

        if res["status"] in (resolver.EXACT, resolver.FUZZY):
            actions.append(inventory.apply_movement(
                shop_id, res["sku"], direction,
                item["qty"], item.get("unit", ""), item.get("price_rupees"),
            ))
            continue

        if res["status"] == resolver.ASK:
            item["direction"] = direction
            _save_pending(shop_id, sender, reply.ask_which(item["name"], res["candidates"]),
                          res["candidates"], item)
            out = {
                "reply": reply.ask_which(item["name"], res["candidates"]),
                "needs_answer": True,
                "options": [{"label": c["name"], "value": f"sku:{c['id']}"}
                            for c in res["candidates"]] + [
                               {"label": "Naya item hai", "value": "new"}],
                "actions": actions,
                "debug": {"intent": parsed["intent"], "matched_via": "ask"},
            }
            break

        item["direction"] = direction
        _save_pending(shop_id, sender, reply.offer_new(item["name"]), [], item)
        out = {
            "reply": reply.offer_new(item["name"]),
            "needs_answer": True,
            "options": [{"label": "Haan, add karo", "value": "new"},
                        {"label": "Nahi", "value": "cancel"}],
            "actions": actions,
            "debug": {"intent": parsed["intent"], "matched_via": "new"},
        }
        break

    if out is None:
        out = {
            "reply": reply.confirm(actions) if actions else reply.not_understood(),
            "needs_answer": False,
            "actions": actions,
            "debug": {"intent": parsed["intent"],
                      "matched_via": "alias" if actions else "none"},
        }

    out["transcript"] = transcript
    _log_message(shop_id, sender, "out", out["reply"])
    return out
