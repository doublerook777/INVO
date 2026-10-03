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
from .units import to_canonical

# Only these intents ever touch the ledger. A "query" or "unknown" message
# can still parse out something that looks like an item -- "2 kg aata
# chahiye" ("I need 2kg atta") parses an item, but it means a request, not
# a delivery -- and must never silently book a movement.
MOVEMENT_INTENTS = {"stock_in", "stock_out"}

CANCEL_WORDS = {"cancel", "nahi", "no", "na"}
# Free-text equivalents so WhatsApp users who type instead of tapping a
# button still work -- the sandbox has no tappable buttons. These only kick
# in when there are no real candidates to confuse them with: "haan" after
# "Amul ka matlab Butter ya Milk?" is not an answer, and treating it as one
# used to create a junk "Amul" SKU and alias it permanently.
NEW_WORDS_LOOSE = {"haan", "haan, add karo", "yes", "ha", "add karo"}
UNIT_CONFIRM_WORDS = {"confirm_unit", "haan", "yes", "ha", "ok", "theek hai"}


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


def _save_pending(shop_id, sender, question, candidates, payload):
    _clear_pending(shop_id, sender)
    db.execute(
        """INSERT INTO pending_asks
           (shop_id, sender, question, candidates_json, raw_item_json)
           VALUES (?, ?, ?, ?, ?)""",
        (shop_id, sender, question, json.dumps(candidates), json.dumps(payload)),
    )


def _done(actions):
    return {
        "reply": reply.confirm(actions) if actions else reply.not_understood(),
        "needs_answer": False,
        "actions": actions,
        "debug": {"matched_via": "alias" if actions else "none"},
    }


def _process_items(shop_id, sender, items, direction, actions=None):
    """Walk items in order, applying each resolved one. The moment one needs
    clarification (ambiguous SKU, brand-new item, or an unconvertible unit),
    this stops and saves a pending question -- the *remaining* items and
    *actions already booked* travel inside that pending row, so answering the
    question resumes right where it left off instead of losing the rest of
    the message.
    """
    actions = list(actions or [])

    for idx, item in enumerate(items):
        remaining = items[idx + 1:]
        res = resolver.resolve(shop_id, item["name"])

        if res["status"] in (resolver.EXACT, resolver.FUZZY):
            sku = res["sku"]
            qty_canon, confident = to_canonical(
                item["qty"], item.get("unit", ""), sku["canonical_unit"], sku["name"])

            if not confident:
                # units.py's own contract: "the caller should ask the user
                # rather than guess". Nothing used to act on this -- a
                # garbled unit silently wrote a wrong number to the ledger
                # with only a footnote in the reply. Ask instead of guessing.
                question = reply.confirm_unit(item["qty"], item.get("unit", ""),
                                               sku["name"], sku["canonical_unit"])
                item["direction"] = direction
                _save_pending(shop_id, sender, question, [], {
                    "reason": "unit_ask", "item": item, "sku_id": sku["id"],
                    "remaining": remaining, "actions_so_far": actions,
                })
                return {
                    "reply": question,
                    "needs_answer": True,
                    "options": [
                        {"label": reply.confirm_unit_label(item["qty"], sku["canonical_unit"]),
                         "value": "confirm_unit"},
                        {"label": "Nahi, cancel karo", "value": "cancel"},
                    ],
                    "actions": actions,
                    "debug": {"intent": direction, "matched_via": "unit_ask"},
                }

            actions.append(inventory.apply_movement(
                shop_id, sku, direction, item["qty"], item.get("unit", ""),
                item.get("price_rupees")))
            continue

        item["direction"] = direction

        if res["status"] == resolver.ASK:
            question = reply.ask_which(item["name"], res["candidates"])
            _save_pending(shop_id, sender, question, res["candidates"], {
                "reason": "sku_ask", "item": item,
                "remaining": remaining, "actions_so_far": actions,
            })
            return {
                "reply": question,
                "needs_answer": True,
                "options": [{"label": c["name"], "value": f"sku:{c['id']}"}
                            for c in res["candidates"]] + [
                               {"label": "Naya item hai", "value": "new"}],
                "actions": actions,
                "debug": {"intent": direction, "matched_via": "ask"},
            }

        question = reply.offer_new(item["name"])
        _save_pending(shop_id, sender, question, [], {
            "reason": "new_offer", "item": item,
            "remaining": remaining, "actions_so_far": actions,
        })
        return {
            "reply": question,
            "needs_answer": True,
            "options": [{"label": "Haan, add karo", "value": "new"},
                        {"label": "Nahi", "value": "cancel"}],
            "actions": actions,
            "debug": {"intent": direction, "matched_via": "new"},
        }

    return _done(actions)


def _answer_pending(shop_id, sender, text, pending):
    """User just answered a clarifying question.

    Returns None if `text` doesn't actually look like an answer to the
    pending question (an empty message, a stray "sku:abc", a completely
    unrelated sentence). The caller then treats it as a brand-new message
    instead of silently discarding what the user actually said.
    """
    payload = json.loads(pending["raw_item_json"])
    candidates = json.loads(pending["candidates_json"])
    reason = payload["reason"]
    item = payload["item"]
    remaining = payload["remaining"]
    actions_so_far = payload["actions_so_far"]
    direction = item.get("direction", "in")
    choice = (text or "").strip().lower()

    # Cleared unconditionally, even on the "fall through" paths below -- once
    # a message doesn't look like a real answer, the question is abandoned,
    # not left lingering to be silently re-tried against the next message.
    _clear_pending(shop_id, sender)

    if choice and choice in CANCEL_WORDS:
        reply_text = reply.cancelled()
        if actions_so_far:
            reply_text = reply.confirm(actions_so_far) + "\n" + reply_text
        return {"reply": reply_text, "needs_answer": False, "actions": actions_so_far,
                "debug": {"matched_via": "cancelled"}}

    if reason == "unit_ask":
        if choice and choice in UNIT_CONFIRM_WORDS:
            sku = db.query_one("SELECT * FROM skus WHERE id = ?", (payload["sku_id"],))
            # Force the raw==canonical fast path: the user just confirmed the
            # stated quantity IS the canonical unit, so no conversion guess.
            action = inventory.apply_movement(
                shop_id, sku, direction, item["qty"], sku["canonical_unit"],
                item.get("price_rupees"))
            return _process_items(shop_id, sender, remaining, direction,
                                   actions_so_far + [action])
        return None  # not a recognized answer -- fall through, don't swallow it

    # reason is "sku_ask" or "new_offer"
    sku, created = None, False
    if choice == "new" or (not candidates and choice in NEW_WORDS_LOOSE):
        sku = inventory.create_sku(shop_id, item["name"], item.get("unit", ""))
        created = True
    elif choice.startswith("sku:"):
        try:
            sku_id = int(choice[4:])
        except ValueError:
            return None  # "sku:abc" -- not a real answer, don't crash on it
        sku = db.query_one("SELECT * FROM skus WHERE id = ?", (sku_id,))
    elif choice:  # guard empty string -- "" is a substring of everything
        for c in candidates:
            if choice in c["name"].lower() or c["name"].lower().startswith(choice):
                sku = db.query_one("SELECT * FROM skus WHERE id = ?", (c["id"],))
                break

    if not sku:
        return None  # didn't match anything -- fall through, don't swallow it

    resolver.learn_alias(shop_id, sku["id"], item["name"])
    log(f"learned alias: '{item['name']}' -> {sku['name']}")
    action = inventory.apply_movement(
        shop_id, sku, direction, item["qty"], item.get("unit", ""), item.get("price_rupees"))
    actions = actions_so_far + [action]

    result = _process_items(shop_id, sender, remaining, direction, actions)
    if not result.get("needs_answer"):
        if created:
            result["reply"] = f"{reply.created_new(sku['name'])}\n{result['reply']}"
        else:
            result["reply"] += f"\nAb se '{item['name']}' yaad rahega."
    result.setdefault("debug", {})["matched_via"] = "new_sku" if created else "user_answer"
    return result


def handle_message(shop_id, sender, text=None, transcript=None):
    """Main entry point. Returns the dict in docs/api-contract.md."""
    body = text or transcript or ""
    _log_message(shop_id, sender, "in", body)

    pending = _get_pending(shop_id, sender)
    if pending:
        result = _answer_pending(shop_id, sender, body, pending)
        if result is not None:
            result["transcript"] = transcript
            _log_message(shop_id, sender, "out", result["reply"])
            return result
        # Didn't look like an answer at all -- the user moved on to
        # something else. Process it as a fresh message instead of
        # discarding it; the old question is already gone (_answer_pending
        # cleared it whenever it decided not to match).

    parsed = extract_mod.extract(body)

    if parsed["intent"] not in MOVEMENT_INTENTS:
        # Never book a movement for a query or an unclear message, even if
        # the extractor still parsed something that looks like an item.
        out = {
            "reply": reply.query_reply() if parsed["intent"] == "query" else reply.not_understood(),
            "needs_answer": False,
            "actions": [],
            "debug": {"intent": parsed["intent"], "matched_via": "none",
                      "extract_source": parsed.get("_source")},
        }
        out["transcript"] = transcript
        _log_message(shop_id, sender, "out", out["reply"])
        return out

    direction = "out" if parsed["intent"] == "stock_out" else "in"
    out = _process_items(shop_id, sender, parsed.get("items", []), direction)
    out["debug"]["intent"] = parsed["intent"]
    out["debug"]["extract_source"] = parsed.get("_source")
    out["transcript"] = transcript
    _log_message(shop_id, sender, "out", out["reply"])
    return out
