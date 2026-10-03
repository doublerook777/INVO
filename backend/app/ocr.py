"""Supplier bill photo -> text.  DEV B OWNS THIS FILE.

This is the FIRST thing on the cut list. Do not start it until the chat flow and
the dashboard are both done and screenshotted.

TODO(Dev B): Gemini vision -- same key as extraction, one less thing to set up.
Send the image and ask for the line items; the normal extract -> resolve pipeline
handles the rest, so you only need to return plain text here.
"""
from .config import GEMINI_API_KEY, log


async def read_bill(image_bytes, mime="image/jpeg"):
    if not GEMINI_API_KEY:
        log("ocr: no gemini key")
        return None
    raise NotImplementedError("TODO(Dev B): Gemini vision call")
