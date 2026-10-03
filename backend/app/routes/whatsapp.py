"""Twilio WhatsApp webhook.  DEV B OWNS THIS FILE.

Rule: NO business logic here. This file translates Twilio's form fields into a
call to the same handle_message() the web UI uses, and turns the answer into
TwiML. If you're writing an `if` about inventory, it belongs in pipeline.py.

What lives here is transport work only: downloading a voice note from Twilio,
handing it to asr.py, and spelling out the answer choices in words (WhatsApp
sandbox has no tappable buttons).

Setup:
    ngrok http 8000
    Twilio console -> WhatsApp sandbox -> "When a message comes in":
        https://<your-ngrok>.ngrok-free.app/api/whatsapp/webhook   (POST)
"""
import httpx
from fastapi import APIRouter, Form
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from .. import asr
from ..config import DEMO_SHOP_ID, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, log
from ..core import pipeline

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

MAX_MEDIA_BYTES = 15 * 1024 * 1024   # same guard as routes/chat.py

AUDIO_FAILED = "Audio samajh nahi aaya. Type karke bhejiye?"
MEDIA_UNSUPPORTED = "Abhi sirf text ya voice note samajh aata hai. Type karke bhejiye?"
SERVER_ERROR = "Kuch gadbad ho gayi. Thodi der baad dobara bhejiye."


def _twiml(text):
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?>'
                f"<Response><Message>{safe}</Message></Response>",
        media_type="text/xml",
    )


def _num_media(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def _fetch_media(url):
    """Download a Twilio media file. Returns bytes, or None on any failure.

    Twilio media URLs need HTTP basic auth (account SID + auth token) and then
    redirect to a CDN. httpx applies `auth` to the first request only and
    follows the redirect without it, which is what we want.
    """
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        log("whatsapp: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set, can't fetch media")
        return None
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            async with client.stream(
                "GET", url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            ) as r:
                r.raise_for_status()
                data = bytearray()
                async for chunk in r.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_MEDIA_BYTES:
                        log("whatsapp: media over size cap, dropping")
                        return None
                return bytes(data)
    except Exception as e:
        # Log type + status only: httpx error text carries the full media URL.
        status = getattr(getattr(e, "response", None), "status_code", None)
        log(f"whatsapp: media download failed ({type(e).__name__}"
            f"{f', HTTP {status}' if status else ''})")
        return None


def _answer_hint(options):
    """WhatsApp has no buttons, so say in words what the user can type.

    Maps the contract's option values to something typable: `sku:<id>` becomes
    the item's label, `new`/`cancel`/`confirm_unit` become plain words that
    pipeline.py already accepts as free text.
    """
    words = []
    for o in options or []:
        value = o.get("value", "")
        if value.startswith("sku:"):
            words.append(o["label"])
        elif value == "new":
            words.append("new")
        elif value == "cancel":
            words.append("nahi")
        elif value == "confirm_unit":
            words.append("haan")
    words = list(dict.fromkeys(words))
    return f"\n(Jawab likhiye: {' / '.join(words)})" if words else ""


@router.post("/webhook")
async def webhook(From: str = Form(""), Body: str = Form(""),
                  NumMedia: str = Form("0"), MediaUrl0: str = Form(""),
                  MediaContentType0: str = Form("")):
    log(f"whatsapp in from {From}: {Body!r} media={NumMedia} {MediaContentType0}")

    transcript = None
    if _num_media(NumMedia) > 0:
        if not MediaContentType0.startswith("audio/"):
            if not Body.strip():
                return _twiml(MEDIA_UNSUPPORTED)
        else:
            audio = await _fetch_media(MediaUrl0)
            if audio:
                transcript = await asr.transcribe(
                    audio, "note." + MediaContentType0.split("/")[1].split(";")[0],
                    mime_type=MediaContentType0.split(";")[0], shop_id=DEMO_SHOP_ID)
            if not transcript and not Body.strip():
                return _twiml(AUDIO_FAILED)

    try:
        result = await run_in_threadpool(
            pipeline.handle_message, DEMO_SHOP_ID, From,
            text=Body or None, transcript=transcript)
    except Exception as e:
        log("whatsapp: pipeline crashed:", e)
        return _twiml(SERVER_ERROR)

    text = result["reply"]
    if transcript:
        text = f'🎙 "{transcript}"\n{text}'
    if result.get("needs_answer"):
        text += _answer_hint(result.get("options"))
    return _twiml(text)
