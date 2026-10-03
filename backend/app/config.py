"""All environment config in one place. Import from here, never os.getenv elsewhere."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")

DB_PATH = BASE_DIR / os.getenv("DB_PATH", "stocksaathi.db")
DEMO_SHOP_ID = int(os.getenv("DEMO_SHOP_ID", "1"))

# Resolver thresholds -- tune these during the demo, they matter a lot.
FUZZY_AUTO_ACCEPT = 85.0   # >= this, use the match silently
FUZZY_ASK_FLOOR = 60.0     # between floor and auto-accept, ask the user once
TIE_MARGIN = 5.0           # if the top two are this close, ask even if both score high

LOW_STOCK_DAYS = 4.0       # days of cover below which we nag


def log(*args):
    """Use this instead of print, so demo output is greppable."""
    print("[stocksaathi]", *args, flush=True)
