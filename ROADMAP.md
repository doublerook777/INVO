# Roadmap

## Goal

A shop owner runs their stock register from WhatsApp, by voice or text, in
Hinglish. Three things have to work, and everything below is ordered by them:

1. **A Hinglish voice note or message becomes a clean stock confirmation.**
2. **The bot asks a clarifying question once, then remembers the answer.**
   This is the main differentiator, so it must be visible.
3. **A dashboard** with the live stock table and a red low-stock alert, so the
   bot speaks first when something is about to run out.

If scope has to shrink, we cut features and never these three flows.

---

## Ground rules

- **The API contract is frozen.** Nobody changes a field name without telling
  the other person. See `docs/api-contract.md`.
- **Frontend never waits for backend.** The backend ships stub endpoints that
  return correctly shaped JSON, so the UI can be built against them and keeps
  working when the real logic lands.
- **Update `PROGRESS.md` after every chunk.** Both of us use AI agents that run
  out of context. That file is how the next session picks up.
- **Commit small, push often.** See `GIT_WORKFLOW.md`.
- **Demo data is a feature.** The low-stock alert cannot fire without sales
  history, so seed it early.

---

## Work split

The split is chosen so the two halves touch **almost no shared files**. Merge
conflicts cost more than they look like they should.

### Dev A — "the brain" (Ayush)
Owns everything in `backend/app/core/` plus the database.

Understanding a messy message and turning it into correct numbers in a table.

### Dev B — "the face & the edges"
Owns everything in `frontend/` plus `backend/app/asr.py`, `ocr.py`, `routes/whatsapp.py`.

Everything the user sees, plus getting voice, photos and WhatsApp in.

**The only shared file is `backend/app/routes/chat.py`**, which Dev A wrote
first. After that it shouldn't need to change.

---

## Phases

### Phase 0 — Setup and contract lock (both, together)
- [ ] Both clone the repo, both get the backend running (even empty)
- [ ] Read `docs/api-contract.md` together. Change anything that looks wrong
      **now**, then freeze it.
- [ ] Dev A pushes stub endpoints that return fake-but-valid JSON
- [ ] Decide who has a Google Gemini API key and who has a Sarvam key
- [ ] Dev B starts the Twilio sandbox signup early. It is the most likely thing
      to block us.

### Phase 1 — Foundations (parallel)

**Dev A**
- [ ] `db.py` — SQLite schema: shops, skus, aliases, stock_ledger, messages
- [ ] `seed.py` — demo shop, ~30 real kirana SKUs, **14 days of fake sales history**
- [ ] `units.py` — canonical unit per SKU + conversion table (peti/pav/bori/dozen)
- [ ] `inventory.py` — apply a stock-in / stock-out, read current levels
- [ ] Endpoint `GET /api/inventory` returns real data

**Dev B**
- [ ] `frontend/index.html` — WhatsApp-style chat UI. Green bubbles, right-aligned
      user, left-aligned bot, timestamps, a phone frame. **Make it look real.**
- [ ] Wire it to `POST /api/chat` (still stubbed — fine)
- [ ] Text input working end to end

**Checkpoint:** we can type a message in a WhatsApp-looking UI and get a reply
back, and the stock table has data in it.

### Phase 2 — Intelligence (parallel)

**Dev A**
- [ ] `extract.py` — Gemini call with a **fixed JSON schema** (structured output,
      not "please return JSON"). Hinglish in → intent + items + qty + unit + price out
- [ ] `resolver.py` — match extracted item text to a SKU:
      - exact alias hit → use it
      - fuzzy score above threshold → use it
      - in between → **ask the user once, then write the alias row**
      - nothing close → offer to create a new SKU
- [ ] `reorder.py` — days-of-cover: avg daily sales → days remaining. Not ML.
- [ ] Wire all of it into `pipeline.py` so `/api/chat` is real

**Dev B**
- [ ] `dashboard.html` — stock table, low-stock rows in red, a couple of stat cards
- [ ] `asr.py` — voice note → text (Sarvam first, Whisper fallback)
- [ ] Mic button in the chat UI, or at minimum: upload an audio file
- [ ] `routes/whatsapp.py` webhook + ngrok, if Twilio access came through

**Checkpoint:** a real Hinglish sentence updates real stock.

### Phase 3 — Integration (both)
Stop building. Start connecting.

- [ ] Run the full flow 10 times with different phrasings. Fix what breaks.
- [ ] Make the clarify-once flow work end to end
- [ ] Make sure the low-stock alert appears on the dashboard
- [ ] Bot replies should be in Hinglish and look friendly, not like JSON

### Phase 4 — Polish and showcase
- [ ] Clean the demo shop data — no "test test test" rows, no `foo`
- [ ] Run the three key flows and capture high-resolution screenshots
- [ ] Save them to `screenshots/`
- [ ] Commit and push everything

---

## If scope has to shrink (cut in this order)

1. **Bill photo OCR** — least load-bearing
2. **Real Twilio/WhatsApp** — the web chat UI shows the same flow. The adapter
   stays in the code, so it can be switched on later.
3. **Voice input** — fall back to typing the Hinglish text. Still exercises the
   hard part
4. **Dashboard** — the chat alone can carry the product

Never cut: the extraction, the SKU resolver, the seeded history.

## Not building (decided, don't relitigate)

- Barcode scanning — most kirana items aren't barcoded, it's a rabbit hole
- User auth / multi-tenant login — one hardcoded demo shop
- Payments, GST, billing
- A mobile app
