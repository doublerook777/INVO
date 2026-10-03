"""POST /api/chat -- the single entry point.

SHARED FILE. Dev A wrote it in the first 30 minutes; it shouldn't need to change.
If you think it does, message the other dev before editing.

Accepts EITHER a JSON body (text-only, per docs/api-contract.md) or a multipart
form (needed for audio/image uploads) -- branches on Content-Type since FastAPI
can't type both onto one signature.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import asr, ocr
from ..config import DEMO_SHOP_ID, log
from ..core import pipeline

router = APIRouter(prefix="/api", tags=["chat"])

# Nowhere near what a real voice note or bill photo needs -- this is a guard
# against something going wrong, not a real-world limit.
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _error(status, message):
    return JSONResponse(status_code=status, content={"error": message})


async def _read_capped(upload):
    data = await upload.read()
    return None if len(data) > MAX_UPLOAD_BYTES else data


@router.post("/chat")
async def chat(request: Request):
    content_type = request.headers.get("content-type", "")

    try:
        if content_type.startswith("application/json"):
            payload = await request.json()
            shop_id = int(payload.get("shop_id", DEMO_SHOP_ID))
            sender = payload.get("sender", "web-demo")
            text = payload.get("text")
            audio = image = None
        else:
            form = await request.form()
            shop_id = int(form.get("shop_id", DEMO_SHOP_ID))
            sender = form.get("sender", "web-demo")
            text = form.get("text") or None
            audio = form.get("audio") or None
            image = form.get("image") or None
    except Exception as e:
        return _error(400, f"bad request body: {e}")

    transcript = None
    ocr_text = None

    if audio is not None and hasattr(audio, "read"):
        audio_bytes = await _read_capped(audio)
        if audio_bytes is None:
            return _error(413, "audio file too large")
        transcript = await asr.transcribe(audio_bytes, audio.filename or "note.ogg",
                                           mime_type=audio.content_type, shop_id=shop_id)
        if not transcript:
            return {"reply": "Audio samajh nahi aaya. Type karke bhejiye?",
                    "transcript": None, "needs_answer": False, "actions": []}

    if image is not None and hasattr(image, "read"):
        image_bytes = await _read_capped(image)
        if image_bytes is None:
            return _error(413, "image file too large")
        try:
            ocr_text = await ocr.read_bill(image_bytes, image.content_type)
        except NotImplementedError:
            return {"reply": "Bill padhna abhi nahi aata. Type karke bhejiye?",
                    "transcript": None, "needs_answer": False, "actions": []}
        except Exception as e:
            log("chat: ocr failed:", e)
            return {"reply": "Bill padhne mein dikkat aa gayi. Type karke bhejiye?",
                    "transcript": None, "needs_answer": False, "actions": []}

    # Typed text wins -- an attached bill shouldn't silently clobber something
    # the owner actually typed in the same message.
    final_text = text or ocr_text

    if not (final_text or transcript):
        return _error(400, "send one of: text, audio, image")

    log(f"chat from {sender}: {final_text or transcript!r}")
    try:
        return pipeline.handle_message(shop_id, sender, text=final_text, transcript=transcript)
    except Exception as e:
        log("chat: pipeline crashed:", e)
        return _error(500, "internal error, check server log")
