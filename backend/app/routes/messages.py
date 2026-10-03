"""Read-only message log, for the WhatsApp mirror page.  DEV B OWNS THIS FILE.

Why this exists: the Twilio trial account accepts inbound WhatsApp messages but
won't deliver our replies back to the phone. Every in/out message is already
written to the `messages` table by the pipeline, so this just exposes it and
the web UI (frontend/whatsapp.html) can show the conversation the phone can't.
"""
from fastapi import APIRouter

from .. import db
from ..config import DEMO_SHOP_ID

router = APIRouter(prefix="/api", tags=["messages"])


@router.get("/messages")
def get_messages(shop_id: int = DEMO_SHOP_ID, sender: str = "",
                 after_id: int = 0, limit: int = 200):
    """Messages in id order. `sender` is an exact match; empty means every
    WhatsApp sender (`whatsapp:...`), so web-demo chats don't leak in.
    `after_id` lets the page poll for just what's new."""
    limit = max(1, min(limit, 500))
    if sender:
        where, params = "sender = ?", [sender]
    else:
        where, params = "sender LIKE 'whatsapp:%'", []
    rows = db.query(
        f"""SELECT id, sender, direction, body, media_type, created_at
            FROM messages
            WHERE shop_id = ? AND id > ? AND {where}
            ORDER BY id LIMIT ?""",
        (shop_id, after_id, *params, limit),
    )
    return {"messages": rows}
