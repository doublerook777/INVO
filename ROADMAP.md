# Roadmap — 6 hours to a screenshot

## The goal, stated honestly

Round 1 needs **a PPT with a screenshot of the project**. So the single most
important output of these 6 hours is not "a working product" — it is
**2–3 screenshots that make a judge believe this works.**

Everything below is ordered by that. If we run out of time, we cut features,
never the screenshot.

### What the screenshots must show

1. **A WhatsApp chat** where a voice note / Hinglish message turns into a clean
   stock confirmation. (The hero shot.)
2. **The bot asking a clarifying question once** and then remembering the answer.
   (This is our differentiator — it must be visible.)
3. **A dashboard** with the live stock table and a red low-stock alert.

---

## Ground rules for the 6 hours

- **The API contract is frozen at T+0:30.** After that, nobody changes a field
  name without telling the other person. See `docs/api-contract.md`.
- **Dev B never waits for Dev A.** The backend ships stub endpoints that return
  hardcoded-but-correctly-shaped JSON in the first 30 minutes. Dev B builds the
  whole UI against the stubs, and it keeps working when the real logic lands.
- **Update `PROGRESS.md` after every chunk.** Both of us are using AI agents that
  will run out of context. That file is how the next session picks up.
- **Commit every ~30 minutes.** Small commits, push often. Don't lose work.
- **Demo data is a feature, not an afterthought.** The low-stock alert cannot fire
  without history. Seed it early (T+1:30), not at the end.

---

## Work split

The split is chosen so the two halves touch **almost no shared files**. Merge
conflicts cost more than they look like they should at hour 5.

### Dev A — "the brain" (Ayush)
Owns everything in `backend/app/core/` plus the database.

Understanding a messy message and turning it into correct numbers in a table.

### Dev B — "the face & the edges"
Owns everything in `frontend/` plus `backend/app/asr.py`, `ocr.py`, `routes/whatsapp.py`.

Everything the judge actually sees, plus getting voice and WhatsApp in.

**The only shared file is `backend/app/routes/chat.py`**, and Dev A writes it in
the first 30 minutes. After that it shouldn't need to change.

---

## Hour by hour

### T+0:00 → T+0:30 — Setup & contract lock (BOTH, together)
Do this on a call. Do not split up yet.

- [ ] Both clone the repo, both get the backend running (even empty)
- [ ] Read `docs/api-contract.md` out loud together. Change anything that looks
      wrong **now**. Then freeze it.
- [ ] Dev A pushes stub endpoints that return fake-but-valid JSON
- [ ] Decide: who has a Google Gemini API key? Who has a Sarvam key? Get them now.
- [ ] Dev B starts the Twilio sandbox signup **in a background tab** — it is the
      single most likely thing to block us, so start it before we need it

### T+0:30 → T+2:00 — Parallel build, round 1

**Dev A**
- [ ] `db.py` — SQLite schema: shops, skus, aliases, stock_ledger, messages
- [ ] `seed.py` — demo shop, ~30 real kirana SKUs, **14 days of fake sales history**
- [ ] `units.py` — canonical unit per SKU + conversion table (peti/pav/bori/dozen)
- [ ] `inventory.py` — apply a stock-in / stock-out, read current levels
- [ ] Endpoint `GET /api/inventory` returns real data

**Dev B**
- [ ] `frontend/index.html` — WhatsApp-style chat UI. Green bubbles, right-aligned
      user, left-aligned bot, timestamps, a fake phone frame. **Make it look real.**
- [ ] Wire it to `POST /api/chat` (still stubbed — fine)
- [ ] Text input working end to end

**Checkpoint at T+2:00:** we can type a message in a WhatsApp-looking UI and get a
reply back. Stock table has data in it. *This alone is already a screenshot.*

### T+2:00 → T+3:30 — Parallel build, round 2

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
- [ ] If Twilio came through: `routes/whatsapp.py` webhook + ngrok

**Checkpoint at T+3:30:** a real Hinglish sentence updates real stock.

### T+3:30 → T+4:30 — Integration (BOTH)
Stop building. Start connecting.

- [ ] Run the full flow 10 times with different phrasings. Fix what breaks.
- [ ] Make the clarify-once flow actually work end to end — this is the money shot
- [ ] Make sure the low-stock alert appears on the dashboard
- [ ] Bot replies should be in Hinglish and should look friendly, not like JSON

### T+4:30 → T+5:15 — Screenshots & polish
- [ ] Clean the demo shop data — no "test test test" rows, no `foo`
- [ ] Run the three hero flows, take screenshots at **high resolution**
- [ ] Save them to `screenshots/`
- [ ] Commit and push everything

### T+5:15 → T+6:00 — PPT & buffer
- [ ] Slide 2 Solution, Slide 3 Tech Stack, Slide 5 Data Flow, Slide 6 Screenshots
- [ ] Buffer for the thing that will inevitably break

---

## Cut list (in this order, if we fall behind)

1. **Bill photo OCR** — cut first, it's the least load-bearing
2. **Real Twilio/WhatsApp** — the web chat UI screenshots identically. Cut it and
   say "WhatsApp Cloud API integration" on the slide, because the adapter is there
3. **Voice input** — fall back to typing the Hinglish text. Still demos the hard part
4. **Dashboard** — chat alone can carry the screenshot

Never cut: the extraction, the SKU resolver, the seeded history.

## Not building (decided, don't relitigate)

- Barcode scanning — most kirana items aren't barcoded, it's a rabbit hole
- User auth / multi-tenant login — one hardcoded demo shop
- Payments, GST, billing
- A mobile app
