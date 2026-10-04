"""The orchestrator. Every message -- WhatsApp, web, curl -- comes through here.

This function knows nothing about WhatsApp. That's deliberate: if one
integration (say Twilio) breaks, we lose a transport, not the product.

Dev A owns this file.
"""
import json
import re

from .. import db
from ..config import log
from . import extract as extract_mod
from . import inventory, reply, resolver
from .reorder import days_of_cover
from .units import to_canonical

# Only these intents ever touch the ledger. A "query" or "unknown" message
# can still parse out something that looks like an item -- "2 kg aata
# chahiye" ("I need 2kg atta") parses an item, but it means a request, not
# a delivery -- and must never silently book a movement.
MOVEMENT_INTENTS = {"stock_in", "stock_out"}

# Words that show up in a stock question but aren't part of the item name --
# on top of extract.STOP, which already covers most of the verb/particle
# vocabulary for stock_in/out messages.
QUERY_STOP = {"kitna", "kitne", "kitni", "bacha", "bache", "bachi",
              "kya", "dikhao", "batao", "abhi", "left", "available"}

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


def _apply_item(shop_id, sender, sku, item, direction, remaining, actions):
    """Book `item` against a SKU that's no longer in question -- OR ask for
    unit confirmation first if the stated unit doesn't convert cleanly.

    This is the one place that decides whether a resolved item actually gets
    written. Used both when _process_items finds a SKU directly (alias/fuzzy
    match) and when _answer_pending just learned which SKU the user meant --
    a SKU chosen via a clarifying question is not exempt from the same guard
    against a bad unit conversion. (It used to be: the unit confidence check
    lived only in _process_items, so resolving an item through the ask-once
    flow could silently write a wrong quantity with no guard at all.)
    """
    qty_canon, confident = to_canonical(
        item["qty"], item.get("unit", ""), sku["canonical_unit"], sku["name"])

    if not confident:
        # units.py's own contract: "the caller should ask the user rather
        # than guess". A garbled unit used to silently write a wrong number
        # to the ledger with only a footnote in the reply. Ask instead.
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

    action = inventory.apply_movement(
        shop_id, sku, direction, item["qty"], item.get("unit", ""), item.get("price_rupees"))
    return _process_items(shop_id, sender, remaining, direction, actions + [action])


def _process_items(shop_id, sender, items, direction, actions=None):
    """Walk items in order, applying each resolved one. The moment one needs
    clarification (ambiguous SKU, brand-new item, or an unconvertible unit),
    this stops and saves a pending question -- the *remaining* items and
    *actions already booked* travel inside that pending row, so answering the
    question resumes right where it left off instead of losing the rest of
    the message.
    """
    actions = list(actions or [])
    if not items:
        return _done(actions)

    item, remaining = items[0], items[1:]
    res = resolver.resolve(shop_id, item["name"])

    if res["status"] in (resolver.EXACT, resolver.FUZZY):
        return _apply_item(shop_id, sender, res["sku"], item, direction, remaining, actions)

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


def _answer_pending(shop_id, sender, text, pending):
    """User just answered a clarifying question.

    Returns (result, abandoned_actions).

    `result` is None if `text` doesn't actually look like an answer to the
    pending question (an empty message, a stray "sku:abc", a completely
    unrelated sentence, or a row from a schema this build no longer
    understands). The caller then treats `text` as a brand-new message
    instead of silently discarding what the user actually said.

    `abandoned_actions` carries any movements that were already booked
    earlier in the *same original message* (before the question came up).
    Those writes already happened -- losing their confirmation when we move
    on to something else would make it look like nothing happened when
    something did. The caller folds these into whatever reply comes next.
    """
    # Clear first, before touching the payload at all. A row saved by an
    # older build (a different payload shape) must not wedge this sender
    # with the same crash on every message forever -- if we can't make sense
    # of it, abandon it and treat the incoming text as a fresh message.
    _clear_pending(shop_id, sender)
    try:
        payload = json.loads(pending["raw_item_json"])
        candidates = json.loads(pending["candidates_json"])
        reason = payload["reason"]
        item = payload["item"]
        remaining = payload["remaining"]
        actions_so_far = payload["actions_so_far"]
    except (KeyError, TypeError, ValueError) as e:
        log("pipeline: stale/unreadable pending row, dropping it:", e)
        return None, []

    direction = item.get("direction", "in")
    choice = (text or "").strip().lower()

    if choice and choice in CANCEL_WORDS:
        # Cancel means "skip the item being asked about", not "abandon the
        # rest of the message" -- "do amul aaye aur das maggi aaye" then
        # "cancel" should still book the Maggi.
        if not remaining and not actions_so_far:
            return {"reply": reply.cancelled(), "needs_answer": False, "actions": [],
                    "debug": {"matched_via": "cancelled"}}, []
        result = _process_items(shop_id, sender, remaining, direction, actions_so_far)
        if not result.get("needs_answer"):
            skip_note = f"'{item['name']}' skip kar diya."
            result["reply"] = f"{skip_note}\n{result['reply']}"
        result.setdefault("debug", {})["matched_via"] = "cancelled"
        return result, []

    if reason == "unit_ask":
        if choice and choice in UNIT_CONFIRM_WORDS:
            sku = db.query_one("SELECT * FROM skus WHERE id = ?", (payload["sku_id"],))
            # Force the raw==canonical fast path: the user just confirmed the
            # stated quantity IS the canonical unit, so no conversion guess.
            action = inventory.apply_movement(
                shop_id, sku, direction, item["qty"], sku["canonical_unit"],
                item.get("price_rupees"))
            result = _process_items(shop_id, sender, remaining, direction,
                                     actions_so_far + [action])
            return result, []
        return None, actions_so_far  # not a recognized answer -- fall through

    # reason is "sku_ask" or "new_offer"
    sku, created = None, False
    if choice == "new" or (not candidates and choice in NEW_WORDS_LOOSE):
        sku = inventory.create_sku(shop_id, item["name"], item.get("unit", ""))
        created = True
    elif choice.startswith("sku:"):
        try:
            sku_id = int(choice[4:])
        except ValueError:
            return None, actions_so_far  # "sku:abc" -- not a real answer
        sku = db.query_one("SELECT * FROM skus WHERE id = ?", (sku_id,))
    elif choice:  # guard empty string -- "" is a substring of everything
        for c in candidates:
            if choice in c["name"].lower() or c["name"].lower().startswith(choice):
                sku = db.query_one("SELECT * FROM skus WHERE id = ?", (c["id"],))
                break

    if not sku:
        return None, actions_so_far  # didn't match anything -- fall through

    resolver.learn_alias(shop_id, sku["id"], item["name"])
    log(f"learned alias: '{item['name']}' -> {sku['name']}")
    # Through _apply_item, not a direct apply_movement call -- a SKU chosen
    # via this question still needs its unit checked. The original unit
    # confidence couldn't even be known until just now (different SKUs have
    # different canonical units), so skipping this check here is exactly how
    # it used to slip through.
    result = _apply_item(shop_id, sender, sku, item, direction, remaining, actions_so_far)
    if not result.get("needs_answer"):
        if created:
            result["reply"] = f"{reply.created_new(sku['name'])}\n{result['reply']}"
        else:
            result["reply"] += f"\nAb se '{item['name']}' yaad rahega."
    result.setdefault("debug", {})["matched_via"] = "new_sku" if created else "user_answer"
    return result, []


def _answer_query(shop_id, raw_text):
    """"kitna parle g bacha hai" -> actually look it up, instead of always
    pointing at the dashboard. Only answers when the leftover text resolves
    confidently to one SKU (EXACT/FUZZY) -- a wrong guess on a read is lower
    stakes than a wrong guess on a movement, but still worse than admitting
    we don't know, so an ambiguous or unmatched name falls back same as before.
    """
    tokens = re.sub(r"[.,;!?—–-]+", " ", (raw_text or "").lower()).split()
    name = " ".join(t for t in tokens if t not in extract_mod.STOP and t not in QUERY_STOP).strip()
    if not name:
        return reply.query_reply()

    res = resolver.resolve(shop_id, name)
    if res["status"] not in (resolver.EXACT, resolver.FUZZY):
        return reply.query_reply()

    sku = res["sku"]
    _, cover = days_of_cover(shop_id, sku["id"], sku["current_qty"])
    return reply.stock_level(sku["name"], sku["current_qty"], sku["canonical_unit"], cover)


def handle_message(shop_id, sender, text=None, transcript=None):
    """Main entry point. Returns the dict in docs/api-contract.md."""
    body = text or transcript or ""
    _log_message(shop_id, sender, "in", body)

    abandoned = []
    pending = _get_pending(shop_id, sender)
    if pending:
        result, abandoned = _answer_pending(shop_id, sender, body, pending)
        if result is not None:
            result["transcript"] = transcript
            _log_message(shop_id, sender, "out", result["reply"])
            return result
        # Didn't look like an answer at all -- the user moved on to
        # something else. Process it as a fresh message instead of
        # discarding it; the old question is already gone (_answer_pending
        # cleared it whenever it decided not to match). `abandoned` is any
        # movement that was already booked earlier in the old message --
        # those writes happened, so their confirmation rides along with
        # whatever this fresh message turns into below, instead of vanishing.

    parsed = extract_mod.extract(body)

    if parsed["intent"] not in MOVEMENT_INTENTS:
        # Never book a movement for a query or an unclear message, even if
        # the extractor still parsed something that looks like an item.
        reply_text = reply.not_understood()
        if parsed["intent"] == "query":
            reply_text = _answer_query(shop_id, body)
        out = {
            "reply": reply_text,
            "needs_answer": False,
            "actions": [],
            "debug": {"intent": parsed["intent"], "matched_via": "none",
                      "extract_source": parsed.get("_source")},
        }
    else:
        direction = "out" if parsed["intent"] == "stock_out" else "in"
        out = _process_items(shop_id, sender, parsed.get("items", []), direction)
        out["debug"]["intent"] = parsed["intent"]
        out["debug"]["extract_source"] = parsed.get("_source")

    if abandoned:
        out["reply"] = f"{reply.confirm(abandoned)}\n{out['reply']}"
        out["actions"] = abandoned + out["actions"]

    out["transcript"] = transcript
    _log_message(shop_id, sender, "out", out["reply"])
    return out
