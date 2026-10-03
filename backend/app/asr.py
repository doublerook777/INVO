"""Voice note -> text.  DEV B OWNS THIS FILE.

Sarvam (Saaras) first -- built for code-mixed Hinglish and handles brand
names like "Parle-G" much better than generic models. Whisper as fallback if
the Sarvam key doesn't come through.

Returning None makes the pipeline reply "audio samajh nahi aaya", which is a
fine failure mode -- it never crashes the demo.

NOTE on SARVAM_MODE: Sarvam's docs describe "translit" as "romanization to
Latin script" and "codemix" as "code-mixed text output" without fully
disambiguating which one actually matches our case (Hinglish speech -> Latin
script text like "bees Parle-G aaye", same as the rule extractor expects).
translit is the safer-sounding bet from the description, but this needs a
real audio sample to confirm -- same situation extract.py was in before
testing against a live key turned up real surprises. Test both once you have
a voice note.
"""
import json

import httpx

from .config import DEMO_SHOP_ID, OPENAI_API_KEY, SARVAM_API_KEY, log

SARVAM_URL = "https://api.sarvam.ai/speech-to-text"

# Sarvam deprecated "saarika:v2" (and v2.5) -- that model name 404s now. The
# replacement lives on the same /speech-to-text endpoint under the Saaras
# family. v4 is Sarvam's current recommended default.
SARVAM_MODEL = "saaras:v4"
SARVAM_MODE = "translit"

_MIME_BY_EXT = {
    "ogg": "audio/ogg", "opus": "audio/ogg", "webm": "audio/webm",
    "wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4",
    "aac": "audio/aac", "flac": "audio/flac",
}


def _guess_mime(filename):
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    return _MIME_BY_EXT.get(ext, "application/octet-stream")


async def transcribe(audio_bytes, filename="note.ogg", mime_type=None, shop_id=DEMO_SHOP_ID):
    """mime_type should be the browser/WhatsApp's real content type when known
    (the browser sends webm, WhatsApp sends ogg/opus) -- a hardcoded
    "audio/ogg" on a webm upload risks the API rejecting the mismatch."""
    mime_type = mime_type or _guess_mime(filename)
    failures = []

    if SARVAM_API_KEY:
        try:
            return await _sarvam(audio_bytes, filename, mime_type, shop_id)
        except Exception as e:
            failures.append(f"sarvam: {e}")
            log("asr: sarvam failed:", e)
    if OPENAI_API_KEY:
        try:
            return await _whisper(audio_bytes, filename, mime_type)
        except Exception as e:
            failures.append(f"whisper: {e}")
            log("asr: whisper failed:", e)

    if failures:
        log("asr: all configured backends failed ->", "; ".join(failures))
    else:
        log("asr: no ASR key configured, returning None")
    return None


async def _keyterms(shop_id):
    """Bias Sarvam toward this shop's own catalog -- brand names like
    "Parle-G" or "Aashirvaad" are exactly the words a generic model mishears.
    Keyterms is a v4-only feature, capped at 50 terms / 64 chars each.
    Never let this block transcription if the DB call fails for any reason.
    """
    try:
        from . import db
        rows = db.query(
            "SELECT DISTINCT name FROM skus WHERE shop_id = ? LIMIT 50", (shop_id,))
        names = [r["name"] for r in rows if len(r["name"]) <= 64]
        return json.dumps(names) if names else None
    except Exception as e:
        log("asr: keyterms lookup failed, continuing without them:", e)
        return None


async def _sarvam(audio_bytes, filename, mime_type, shop_id):
    data = {"model": SARVAM_MODEL, "mode": SARVAM_MODE}
    keyterms = await _keyterms(shop_id)
    if keyterms:
        data["keyterms"] = keyterms

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            SARVAM_URL,
            headers={"api-subscription-key": SARVAM_API_KEY},
            files={"file": (filename, audio_bytes, mime_type)},
            data=data,
        )
        r.raise_for_status()
        return r.json().get("transcript")


async def _whisper(audio_bytes, filename, mime_type):
    # No `language` pin -- forcing "hi" tends to push Whisper toward
    # Devanagari output, which is the opposite of what the pipeline expects
    # (Latin-script Hinglish). The prompt is written in the same Latin-script
    # Hinglish we want back; Whisper tends to match a prompt's script/style,
    # which is the more reliable lever here. Confirm once a real key/sample
    # is available.
    prompt = ("Hinglish kirana shop inventory message, e.g. "
              "'bees Parle-G aaye, paanch kilo Aashirvaad Atta'. "
              "Brand names: Parle-G, Maggi, Amul, Aashirvaad, Tata, Fortune.")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": (filename, audio_bytes, mime_type)},
            data={"model": "whisper-1", "prompt": prompt},
        )
        r.raise_for_status()
        return r.json().get("text")
