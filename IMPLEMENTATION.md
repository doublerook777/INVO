# Implementation

Architecture, file structure, tools, and setup. Read this before writing code.

---

## 1. Architecture

### The one idea that shapes everything

**The core never knows what WhatsApp is.**

Everything funnels into one function:

```
handle_message(shop_id, sender, text=None, audio=None, image=None) -> reply_text
```

WhatsApp is one caller. The web chat UI is another caller. A curl command is a
third. They all hit the same `POST /api/chat`.

Why this matters for a hackathon: WhatsApp API access is the single most likely
thing to block us. With this shape, if Twilio fights us at hour 4, we lose a
*transport* and still have a working product to screenshot.

### Flow

```
  WhatsApp (Twilio webhook)          Web chat UI
            |                             |
            +--------------+--------------+
                           |
                    POST /api/chat
                           |
                 +---------v---------+
                 |   pipeline.py     |
                 +---------+---------+
                           |
         +-----------------+-----------------+
         |                 |                 |
     audio?            image?             text
         |                 |                 |
    asr.py            ocr.py                 |
   (Sarvam)        (Gemini vision)           |
         |                 |                 |
         +-----------------+-----------------+
                           |
                      plain text
                           |
                  +--------v--------+
                  |   extract.py    |   LLM + FIXED JSON SCHEMA
                  +--------+--------+   -> {intent, items:[{name,qty,unit,price}]}
                           |
                  +--------v--------+
                  |   resolver.py   |   messy name -> real SKU
                  +--------+--------+   alias hit / fuzzy / ask once / create
                           |
                  +--------v--------+
                  |    units.py     |   peti -> 24 packets, pav -> 0.25 kg
                  +--------+--------+
                           |
                  +--------v--------+
                  |  inventory.py   |   write to stock_ledger
                  +--------+--------+
                           |
                  +--------v--------+
                  |    reply.py     |   Hinglish confirmation
                  +-----------------+

  Separate background job:
      reorder.py  ->  days-of-cover per SKU  ->  nudge when below threshold
```

### Why SQLite and not Postgres + pgvector

We planned pgvector originally. For a 6-hour build it's the wrong call:
setup cost, a service to run, and a dependency that can fail on a laptop at
hour 3.

`rapidfuzz` string matching over a per-shop alias table gets us ~the same
demo quality on kirana item names, with zero infrastructure. Embeddings are a
post-hackathon upgrade, and the resolver interface is written so it can be
swapped without touching anything else.

### The resolver (the actual hard part)

This is what makes the project more than a chatbot wrapper. Three confidence tiers:

| Score | Action |
|---|---|
| exact alias match | use it, say nothing |
| fuzzy >= 85 | use it, say nothing |
| **top two within 5 points** | **ask** — see below |
| 60 – 85 | **ask once**: "Parle-G Biscuit ya Parle Monaco?" → save the answer as an alias |
| < 60 | "Ye naya item hai? Add kar doon?" |

**The near-tie rule matters more than the thresholds.** `amul` scores 90 against
*both* "Amul Butter" and "Amul Taaza Milk"; `tata` ties between Tata Salt and Tata
Tea. Taking the top match silently writes stock against the wrong item and nobody
notices until the numbers are wrong. So when the top two are within `TIE_MARGIN`
(5 points) of each other, we ask regardless of how high they scored.

The alias write is the whole point. **The bot never asks the same question twice.**
Make sure the demo shows this.

---

## 2. File structure

```
stock-saathi/
├── README.md
├── ROADMAP.md               # 6-hour plan + work split
├── IMPLEMENTATION.md        # this file
├── PROGRESS.md              # <-- UPDATE THIS AS YOU WORK
├── .env.example
├── .gitignore
│
├── backend/
│   ├── requirements.txt
│   ├── data/
│   │   └── catalog_seed.json      # ~30 real kirana SKUs        [A]
│   └── app/
│       ├── main.py                # FastAPI app, CORS, routers  [A]
│       ├── config.py              # env vars in one place       [A]
│       ├── db.py                  # sqlite3 schema + helpers    [A]
│       ├── seed.py                # demo shop + 14d history     [A]
│       ├── asr.py                 # audio -> text               [B]
│       ├── ocr.py                 # bill photo -> text          [B]
│       ├── core/
│       │   ├── pipeline.py        # orchestrator                [A]
│       │   ├── extract.py         # LLM -> fixed JSON           [A]
│       │   ├── resolver.py        # name -> SKU + aliases       [A]
│       │   ├── units.py           # unit conversion             [A]
│       │   ├── inventory.py       # apply ledger entries        [A]
│       │   ├── reorder.py         # days of cover               [A]
│       │   └── reply.py           # Hinglish reply strings      [A]
│       └── routes/
│           ├── chat.py            # POST /api/chat   SHARED, A writes first
│           ├── inventory.py       # GET  /api/inventory, /api/alerts  [A]
│           └── whatsapp.py        # Twilio webhook -> chat    [B]
│
├── frontend/                      # no build step, plain files  [B]
│   ├── index.html                 # WhatsApp-style chat
│   ├── dashboard.html             # stock table + alerts
│   ├── app.js
│   ├── dashboard.js
│   └── styles.css
│
├── docs/
│   └── api-contract.md            # FROZEN at T+0:30
│
└── screenshots/                   # the actual Round 1 deliverable
```

`[A]` = Dev A owns it. `[B]` = Dev B owns it. **Don't edit the other person's files.**
If you need a change in their file, message them.

---

## 3. Database schema

```sql
shops          (id, name, owner_phone, created_at)
skus           (id, shop_id, name, canonical_unit, current_qty,
                cost_per_unit, sell_price, reorder_days, created_at)
aliases        (id, shop_id, sku_id, alias_text)      -- the learning table
stock_ledger   (id, shop_id, sku_id, direction, qty_canonical,
                raw_qty, raw_unit, cost_per_unit, source, created_at)
messages       (id, shop_id, sender, direction, body, media_type, created_at)
pending_asks   (id, shop_id, sender, question, candidates_json,
                raw_item_json, created_at)            -- the "ask once" state
```

- `direction` is `in` or `out`.
- `qty_canonical` is always in the SKU's canonical unit. **Always.** Every bug in
  this project's profit math will come from skipping this conversion.
- `pending_asks` is how we remember we asked a question. One row at a time per
  sender keeps it simple.

---

## 4. Tools used

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3 + FastAPI | fast to write, async, auto docs at `/docs` |
| Server | uvicorn | standard |
| DB | SQLite (stdlib `sqlite3`) | zero setup, one file, no service to run |
| Item matching | `rapidfuzz` | fast fuzzy strings, no model to load |
| LLM extraction | Google Gemini | free tier, good at Hinglish, structured output |
| Speech to text | Sarvam (Saarika) | built for Indic + code-mixed Hinglish |
| Fallback ASR | OpenAI Whisper API | if Sarvam key doesn't come through |
| Bill OCR | Gemini vision | same key as extraction, one less thing |
| WhatsApp | Twilio WhatsApp Sandbox | ~15 min to a working two-way loop |
| Frontend | Plain HTML + hand-written CSS | **no build step, no CDN** — works even if the venue wifi dies |
| Tunnel | ngrok | expose localhost to the Twilio webhook |

### Why Twilio sandbox over Meta Cloud API

Meta is the "real" integration and where this would go in production. For today,
Twilio wins on setup time: account → sandbox → send a join code from your phone →
point the webhook at ngrok. Roughly 15 minutes versus Meta's app creation plus
per-tester phone number verification.

A judge cannot tell the difference from a screenshot.

**One thing to know:** WhatsApp only allows free-form business-initiated messages
within 24 hours of the user's last message. Our proactive "stock khatam ho raha hai"
nudge is business-initiated. During a demo this is a non-issue — you'll have
messaged the bot minutes earlier, so the window is open. **Do not burn time on
template approval.** Just don't be surprised if the scheduled job goes quiet after
sitting idle overnight.

Provider limits shift, so check the current docs when you sign up rather than
trusting these numbers.

---

## 5. Setup required before starting

### Everyone

```bash
git clone git@github.com:ayushrai-10/stock-saathi.git
cd stock-saathi
```

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Check it: open `http://localhost:8000/docs` — FastAPI's auto docs. If you see the
endpoint list, backend is alive.

### Frontend

No install. No build.

```bash
cd frontend
python3 -m http.server 5500
```

Open `http://localhost:5500`.

### Keys to get (do this in the first 15 minutes)

| Key | Where | Needed by |
|---|---|---|
| `GEMINI_API_KEY` | aistudio.google.com | Dev A — blocks extraction |
| `SARVAM_API_KEY` | dashboard.sarvam.ai | Dev B — blocks voice |
| `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` | twilio.com console | Dev B — blocks WhatsApp |

The backend runs fine without any of them — extraction falls back to a rule-based
stub so Dev B is never blocked. But get them early.

### ngrok (Dev B, only if doing real WhatsApp)

```bash
ngrok http 8000
# paste the https URL + /api/whatsapp/webhook into the Twilio sandbox config
```

---

## 6. Conventions

- **Money is integer paise**, not floats. `4600` = ₹46.00.
- **Quantities are floats** in the canonical unit.
- All timestamps UTC ISO8601.
- Never `print()` — use the `log` helper so we can read output during the demo.
- The bot replies in **Hinglish, Latin script**. Not English, not Devanagari.
  "20 Parle-G add ho gaye" beats "20 units of Parle-G have been added to inventory."
