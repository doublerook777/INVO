# Progress

**Both devs: update this file as you finish things.** We're both using AI agents
that will run out of context. When a new session starts, this file is the handoff.

How to use it: tick the boxes, and append a one-line entry to the log at the
bottom with the time. Don't write essays — the next agent needs facts, not prose.

---

## Status at a glance

| | Dev A (Ayush) — backend brain | Dev B — interface & edges |
|---|---|---|
| Current task | `extract.py` DONE and verified live. Moving to stub endpoints / docs freeze | ASR + polish the UI |
| Blocked on | nothing | needs `SARVAM_API_KEY` |
| Last commit | Gemini live, model switched to `gemini-3.1-flash-lite` | initial scaffold |

**Overall: T+0:00. Working skeleton committed and tested end to end.**

The scaffold is further along than a blank repo: the chat flow, the resolver, the
seed data and both UI pages already run. What is NOT done is marked `TODO(Dev A)`
/ `TODO(Dev B)` in the code. Search for `TODO(` to find your work.

Verified working right now:
- `aaj bees Parle-G aaye, aur paanch kilo aata, aata ka rate badh gaya - chhiyalis rupaye`
  -> both items booked, 46 saved as the new atta rate
- `do peti coke aaye` -> 48 pieces (unit conversion)
- `do amul aaye` -> bot asks Butter or Milk -> answer -> **asks again? no.**
- 5 items already low, so the alert screenshot has real content

---

## Checklist

### Shared (T+0:00 → T+0:30)
- [x] Scaffold built, tested, pushed
- [ ] Both have the repo cloned and backend running
- [ ] `docs/api-contract.md` read together and frozen
- [ ] Stub endpoints pushed by Dev A
- [ ] Gemini key obtained
- [ ] Sarvam key obtained
- [ ] Twilio sandbox signup started

### Dev A — backend brain
- [x] `db.py` schema created
- [x] `seed.py` — demo shop + 30 SKUs
- [x] `seed.py` — **14 days of fake sales history** (alerts need this)
- [x] `units.py` conversions
- [x] `inventory.py` apply stock in/out
- [x] `GET /api/inventory` returns real data
- [x] `extract.py` — Gemini structured-output call (`responseSchema` pinned, no key -> falls back to rules). **Verified live with a real key, all demo sentences pass.**
- [x] `resolver.py` — alias exact match
- [x] `resolver.py` — fuzzy match
- [x] `resolver.py` — **ask-once flow + alias write**
- [x] `reorder.py` — days of cover
- [x] `reply.py` — Hinglish replies
- [x] `pipeline.py` — all of it wired into `/api/chat`

### Dev B — interface & edges
- [x] `index.html` — WhatsApp-style chat UI
- [x] Chat wired to `POST /api/chat`
- [x] Text message round trip works
- [x] `dashboard.html` — stock table
- [x] Dashboard — low stock rows in red
- [~] `asr.py` — Sarvam + Whisper code written but **never run (no key yet)**
- [x] Voice input in the UI (mic + file-upload fallback) — untested without a key
- [ ] `ocr.py` — bill photo *(cut first if short on time)*
- [~] `routes/whatsapp.py` — text path done; **media download TODO(Dev B)** *(cut second)*
- [ ] ngrok tunnel live

### Endgame (both)
- [ ] Full flow tested 10× with different phrasings
- [ ] Clarify-once flow works end to end
- [ ] Demo data cleaned (no test junk rows)
- [ ] **Screenshot 1** — voice note → stock confirmation
- [ ] **Screenshot 2** — bot asks once, then remembers
- [ ] **Screenshot 3** — dashboard with red low-stock alert
- [ ] Screenshots saved to `screenshots/`
- [ ] Everything pushed
- [ ] PPT slides 2, 3, 5, 6 filled

---

## Decisions made (don't relitigate)

| Decision | Reason |
|---|---|
| Near-tie rule in the resolver | `amul` scores 90 against *both* Butter and Milk; picking the top one silently books the wrong item |
| Hand-written CSS, no Tailwind CDN | venue wifi dying shouldn't take the UI down |
| SQLite, not Postgres+pgvector | 6 hours; no service to run; swap later |
| rapidfuzz, not embeddings | good enough for kirana names, zero setup |
| Plain HTML + Tailwind CDN, no React | no build step to break at hour 5 |
| Twilio sandbox, not Meta Cloud API | ~15 min setup vs. Meta's verification flow |
| Money stored as integer paise | float rupees will produce wrong totals |
| No barcode scanning | most kirana stock isn't barcoded |
| No auth / multi-tenant | one hardcoded demo shop |

---

## Known issues / gotchas hit

_Append as you hit them. Saves the other person an hour._

| Issue | Workaround |
|---|---|
| A wrong fuzzy match gets saved as an alias **permanently** | The near-tie rule prevents the common case. If the demo DB learns something wrong, `python -m app.seed --reset` |
| `g` as a unit collided with item names (`parle g` -> `parle`) | dropped bare `g` from the unit list; `gm`/`gram` still work |
| `gaya`/`gaye` read as a sale, but `rate badh gaya` isn't one | stock-out now needs a `bik`/`bech` prefix or `sold`/`nikla` |
| `pav` is both a unit (0.25 kg) and a word for bread | removed `pav` from the Bread aliases |
| **`gemini-3.8-flash` free tier is only 20 requests/day** -- we burned it in ~15 minutes of testing | Switched `GEMINI_MODEL` in `extract.py` to `gemini-3.1-flash-lite`, which has a much higher free quota. If you add a key and extract() silently falls back to rules every time, check for a 429 in the server log -- that's quota, not a code bug |
| Without an enum on the `unit` field, Gemini invented plausible-looking units like `"units"` that `units.py` doesn't recognize, silently degrading to the low-confidence path | `GEMINI_SCHEMA`'s `unit` field is now constrained to the exact list `units.py` understands (`UNIT_ENUM`), and the prompt tells the model to default to `"packet"` for a bare count |
| Gemini read `"paanch amul bike"` (sold) as `intent: unknown` and folded the verb into the item name | Prompt now explicitly lists which verbs mean `stock_in` vs `stock_out`, matching the same vocabulary `_rule_extract` already used |

---

## Log

Format: `HH:MM — who — what`

```
00:00 — both — repo scaffolded, docs written, pushed
00:00 — both — backend verified end to end: extract -> resolve -> ledger -> reply
00:00 — both — seed produces 32 SKUs, 107 aliases, 14d history, 5 low-stock items
00:30 — A — extract.py: real Gemini call wired (httpx, responseSchema pinned,
         no new dependency). Falls back to rules on any failure.
00:45 — A — tested live with a real GEMINI_API_KEY. gemini-2.0-flash was
         deprecated (404) -> moved to gemini-3.8-flash -> hit its 20/day free
         quota in minutes -> settled on gemini-3.1-flash-lite (higher free
         quota, ~1s latency with thinkingBudget:0). Found and fixed two real
         quality bugs along the way (unit hallucination, stock_out
         misclassified) -- see Known issues. All 3 demo sentences now pass
         live through the real HTTP server, not just the rule fallback.
         DB reset to clean state afterward.
```
