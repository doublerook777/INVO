"""Voice note -> text.  DEV B OWNS THIS FILE.

TODO(Dev B):
  1. Sarvam (Saarika) first -- it's built for code-mixed Hinglish and handles
     brand names like "Parle-G" much better than generic models.
  2. Whisper as fallback if the Sarvam key doesn't come through.

Returning None makes the pipeline reply "audio samajh nahi aaya", which is a
fine failure mode -- it never crashes the demo.
"""
import httpx

from .config import OPENAI_API_KEY, SARVAM_API_KEY, log

SARVAM_URL = "https://api.sarvam.ai/speech-to-text"


async def transcribe(audio_bytes, filename="note.ogg"):
    if SARVAM_API_KEY:
        try:
            return await _sarvam(audio_bytes, filename)
        except Exception as e:
            log("asr: sarvam failed:", e)
    if OPENAI_API_KEY:
        try:
            return await _whisper(audio_bytes, filename)
        except Exception as e:
            log("asr: whisper failed:", e)
    log("asr: no key configured, returning None")
    return None


async def _sarvam(audio_bytes, filename):
    # TODO(Dev B): check current field names against Sarvam's docs before trusting this.
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            SARVAM_URL,
            headers={"api-subscription-key": SARVAM_API_KEY},
            files={"file": (filename, audio_bytes, "audio/ogg")},
            data={"model": "saarika:v2", "language_code": "hi-IN"},
        )
        r.raise_for_status()
        return r.json().get("transcript")


async def _whisper(audio_bytes, filename):
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": (filename, audio_bytes, "audio/ogg")},
            data={"model": "whisper-1"},
        )
        r.raise_for_status()
        return r.json().get("text")
