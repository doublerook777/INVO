"""Twilio WhatsApp webhook.  DEV B OWNS THIS FILE.

Rule: NO business logic here. This file translates Twilio's form fields into a
call to the same handle_message() the web UI uses, and turns the answer into
TwiML. If you're writing an `if` about inventory, it belongs in pipeline.py.

Setup:
    ngrok http 8000
    Twilio console -> WhatsApp sandbox -> "When a message comes in":
        https://<your-ngrok>.ngrok-free.app/api/whatsapp/webhook   (POST)
"""
from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from ..config import DEMO_SHOP_ID, log
from ..core import pipeline

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


def _twiml(text):
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?>'
                f"<Response><Message>{safe}</Message></Response>",
        media_type="application/xml",
    )


@router.post("/webhook")
async def webhook(request: Request, From: str = Form(""), Body: str = Form(""),
                  NumMedia: str = Form("0")):
    log(f"whatsapp in from {From}: {Body!r} media={NumMedia}")

    transcript = None
    if NumMedia and int(NumMedia) > 0:
        # TODO(Dev B): form has MediaUrl0 + MediaContentType0. Fetch the URL with
        # HTTP basic auth (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN), then:
        #     transcript = await asr.transcribe(audio_bytes)
        pass

    result = pipeline.handle_message(DEMO_SHOP_ID, From, text=Body or None,
                                     transcript=transcript)
    return _twiml(result["reply"])
