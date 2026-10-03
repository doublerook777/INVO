"""Message text -> structured intent.

Dev A owns this file.

`_llm_extract` calls Gemini with *structured output against the frozen schema*
below (via `responseSchema`, not a "please return JSON" prompt) so the model
cannot return prose. `_rule_extract` is the fallback when there's no key or the
call fails, so Dev B is never blocked by Gemini being flaky or missing.
"""
import json
import re

import httpx

from ..config import GEMINI_API_KEY, log

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL = "gemini-2.0-flash"

# The frozen output schema. Everything downstream assumes exactly this shape.
SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["stock_in", "stock_out", "query", "answer", "unknown"],
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "qty": {"type": "number"},
                    "unit": {"type": "string"},
                    "price_rupees": {"type": ["number", "null"]},
                },
                "required": ["name", "qty", "unit"],
            },
        },
        "question": {"type": ["string", "null"]},
    },
    "required": ["intent", "items"],
}

# Gemini's `responseSchema` is OpenAPI-ish but not identical to SCHEMA above:
# uppercase type names, `nullable: true` instead of a `type` union. Keep this
# in lockstep with SCHEMA by hand -- there are only four fields, not worth
# writing a converter for.
GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "intent": {
            "type": "STRING",
            "enum": ["stock_in", "stock_out", "query", "answer", "unknown"],
        },
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "qty": {"type": "NUMBER"},
                    "unit": {"type": "STRING"},
                    "price_rupees": {"type": "NUMBER", "nullable": True},
                },
                "required": ["name", "qty", "unit"],
            },
        },
        "question": {"type": "STRING", "nullable": True},
    },
    "required": ["intent", "items"],
}

PROMPT = """You read WhatsApp messages from Indian kirana shop owners. They speak
Hinglish (Hindi written in Latin script, mixed with English). Numbers are often
Hindi words: bees=20, paanch=5, das=10, chhiyalis=46, pachas=50.

Extract what stock came IN, what went OUT, or what they're asking.
Keep item names EXACTLY as the owner said them -- do not translate or correct
spelling. A later step matches them to the catalogue.

Message: {text}"""

HINDI_NUM = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "gyarah": 11, "barah": 12, "pandrah": 15, "bees": 20, "pachchis": 25,
    "tees": 30, "chalis": 40, "chhiyalis": 46, "pachas": 50, "sau": 100,
}

UNITS = {
    "packet", "pkt", "packets", "peti", "crate", "carton", "box", "dozen", "darjan",
    "kg", "kilo", "kilos", "kgs", "gram", "grams", "gm", "pav", "paav",
    "adha", "aadha", "bori", "bora", "litre", "liter", "ltr", "l", "ml",
    "piece", "pieces", "pc", "nos", "adad", "quintal",
}

# Words that end an item name. Mostly verbs and particles.
STOP = {
    "aaye", "aaya", "aya", "aayi", "gaye", "gaya", "gayi", "hai", "hain", "ho",
    "bik", "bika", "bike", "bikre", "bikri", "bech", "becha", "beche",
    "bechi", "bechni", "sold", "nikle",
    "mangaya", "manga", "liya", "diya", "nikla", "mila", "mile", "received",
    "ka", "ki", "ke", "rate", "badh", "ghat", "kam", "zyada", "aur", "and",
    "rupaye", "rupees", "rs", "stock", "mein", "me", "se", "par", "ab", "aaj",
    "kal", "sab", "total", "bhi", "to", "tha", "the", "thi", "hua", "hue",
}

OUT_PREFIXES = ("bik", "bech")   # bika, bike, bikri, becha, bechi...
OUT_WORDS = ("sold", "nikla", "nikle")
IN_WORDS = ("aaye", "aaya", "aya", "mangaya", "liya", "stock", "received", "mila")


def _word_to_num(token):
    return HINDI_NUM.get(token.lower())


def _as_num(token):
    t = token.replace(",", "")
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        return float(t)
    return _word_to_num(t)


def _rule_extract(text):
    """Deterministic fallback -- no API key needed.

    Scans for  <number> [unit] <name words...>  which covers both
    "bees Parle-G aaye" (qty, name, verb) and "paanch kilo aata" (qty, unit, name).
    """
    t = re.sub(r"[.,;!?\u2014\u2013-]+", " ", text.lower())
    tokens = [w for w in t.split() if w]

    sold = any(w in tokens for w in OUT_WORDS) or any(
        w.startswith(OUT_PREFIXES) for w in tokens)
    intent = "stock_out" if sold else (
        "stock_in" if any(w in tokens for w in IN_WORDS) else "query")

    items, price_for_last, i = [], None, 0
    while i < len(tokens):
        qty = _as_num(tokens[i])
        if qty is None:
            i += 1
            continue

        j = i + 1
        # A number right before "rupaye" is a price, not a quantity.
        if j < len(tokens) and tokens[j] in ("rupaye", "rupees", "rs"):
            price_for_last = qty
            i = j + 1
            continue

        unit = ""
        if j < len(tokens) and tokens[j] in UNITS:
            unit, j = tokens[j], j + 1

        name_parts = []
        while j < len(tokens) and tokens[j] not in STOP and _as_num(tokens[j]) is None:
            if tokens[j] in UNITS and name_parts:
                break
            if not name_parts or name_parts[-1] != tokens[j]:
                name_parts.append(tokens[j])
            j += 1
            if len(name_parts) >= 3:   # item names are short; stop running on
                break

        name = " ".join(name_parts).strip()
        if name and len(name) >= 2:
            items.append({"name": name, "qty": qty, "unit": unit or "packet",
                          "price_rupees": None})
        i = max(j, i + 1)

    if price_for_last is not None and items:
        items[-1]["price_rupees"] = price_for_last

    return {"intent": intent if items else "query", "items": items, "question": None}


def _llm_extract(text):
    """Gemini call with structured output pinned to GEMINI_SCHEMA.

    Raises on any failure (bad key, network, malformed response) -- `extract()`
    catches that and falls back to `_rule_extract`. Never let a bad LLM call
    take down the chat turn.
    """
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(text=text)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_SCHEMA,
            "temperature": 0,
        },
    }
    resp = httpx.post(
        GEMINI_URL.format(model=GEMINI_MODEL),
        params={"key": GEMINI_API_KEY},
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    result = json.loads(raw_text)

    if result.get("intent") not in SCHEMA["properties"]["intent"]["enum"]:
        result["intent"] = "unknown"
    result.setdefault("items", [])
    result.setdefault("question", None)
    for item in result["items"]:
        item.setdefault("price_rupees", None)
    return result


def extract(text):
    if not text or not text.strip():
        return {"intent": "unknown", "items": [], "question": None}
    if GEMINI_API_KEY:
        try:
            return _llm_extract(text)
        except Exception as e:
            log("extract: LLM failed, falling back to rules:", e)
    return _rule_extract(text)
