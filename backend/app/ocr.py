"""Supplier bill photo -> text.  DEV B OWNS THIS FILE.

Gemini vision, same key and model as extract.py. We don't parse the bill here:
the model reads the line items and writes them back as ONE Hinglish sentence in
the same style an owner would type ("aaj aaye: 20 packet Parle-G, 5 kg Atta"),
and the normal extract -> resolve -> units -> ledger pipeline takes it from
there. That keeps a single code path for typed text, voice and bills.

Raises on anything that isn't a readable bill. routes/chat.py turns any
exception into a friendly "type karke bhejiye" reply.
"""
import base64

import httpx

from .config import GEMINI_API_KEY, log
from .core.extract import GEMINI_MODEL, GEMINI_URL

NOT_A_BILL = "NOT_A_BILL"

PROMPT = f"""This is a photo of a supplier bill or delivery slip handed to an Indian
kirana shop owner. Read the line items: what was delivered and how much.

Reply with ONE line of plain text, written like the owner would say it:
    aaj aaye: <qty> <unit> <item name>, <qty> <unit> <item name>, ...

Rules:
- Use only these units: packet, piece, kg, gram, litre, ml, dozen, box, peti.
  If the bill gives no unit for an item, use packet.
- Keep item names as printed on the bill (brand + product). No prices, no
  totals, no GST, no bill numbers, no dates.
- Qty is a plain number (20, 2.5), never a word.
- If the photo is not a bill, or you cannot read any line items, reply with
  exactly {NOT_A_BILL} and nothing else.
"""


async def read_bill(image_bytes, mime="image/jpeg"):
    if not GEMINI_API_KEY:
        raise RuntimeError("no GEMINI_API_KEY, can't read bills")
    if not (mime or "").startswith("image/"):
        raise ValueError(f"not an image: {mime!r}")

    body = {
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": mime,
                             "data": base64.b64encode(image_bytes).decode()}},
        ]}],
        "generationConfig": {"temperature": 0},
    }
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={"x-goog-api-key": GEMINI_API_KEY},   # header, never ?key= (leaks in errors)
            json=body,
        )
        r.raise_for_status()

    parts = r.json()["candidates"][0]["content"]["parts"]
    text = " ".join(p.get("text", "") for p in parts).strip().strip("`").strip()
    # Collapse to a single line: the extractor expects one sentence.
    text = " ".join(text.split())
    if not text or NOT_A_BILL in text:
        raise ValueError("no readable line items in image")
    log(f"ocr: read bill -> {text!r}")
    return text
