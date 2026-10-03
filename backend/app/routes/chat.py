"""POST /api/chat -- the single entry point.

SHARED FILE. Dev A wrote it in the first 30 minutes; it shouldn't need to change.
If you think it does, message the other dev before editing.
"""
from fastapi import APIRouter, File, Form, UploadFile

from .. import asr, ocr
from ..config import DEMO_SHOP_ID, log
from ..core import pipeline

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    shop_id: int = Form(DEMO_SHOP_ID),
    sender: str = Form("web-demo"),
    text: str = Form(None),
    audio: UploadFile = File(None),
    image: UploadFile = File(None),
):
    transcript = None

    if audio is not None:
        transcript = await asr.transcribe(await audio.read(), audio.filename or "note.ogg")
        if not transcript:
            return {"reply": "Audio samajh nahi aaya. Type karke bhejiye?",
                    "transcript": None, "needs_answer": False, "actions": []}

    if image is not None:
        try:
            text = await ocr.read_bill(await image.read(), image.content_type)
        except NotImplementedError:
            return {"reply": "Bill padhna abhi nahi aata. Type karke bhejiye?",
                    "transcript": None, "needs_answer": False, "actions": []}

    if not (text or transcript):
        return {"error": "send one of: text, audio, image"}

    log(f"chat from {sender}: {text or transcript!r}")
    return pipeline.handle_message(shop_id, sender, text=text, transcript=transcript)
