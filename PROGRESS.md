# Progress

**Both devs: update this file as you finish things.** We're both using AI agents
that will run out of context. When a new session starts, this file is the handoff.

How to use it: tick the boxes, and append a one-line entry to the log at the
bottom with the time. Don't write essays — the next agent needs facts, not prose.

---

## Status at a glance

| | Dev A (Ayush) — backend brain | Dev B — interface & edges |
|---|---|---|
| Current task | Backend + shared contract solid. Frontend fixed on Dev B's behalf to unblock Screenshot 2 — read `GIT_WORKFLOW.md` before your first commit | `asr.py`, `routes/whatsapp.py`, `ocr.py` — see punch list below |
| Blocked on | nothing | needs `SARVAM_API_KEY` |
| Last commit | Frontend bug fixes + GIT_WORKFLOW.md | initial scaffold |

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
- [x] `pipeline.py` / `inventory.py` — **`new` and `cancel` answers now handled.** Previously the "Naya item hai?" offer had nowhere to go — answering it always fell through to "samajh nahi aaya". Added `inventory.create_sku()` and taught `_answer_pending` to create-and-book on `new`, no-op on `cancel`. Also accepts free-text `haan`/`nahi` etc, since WhatsApp sandbox users type, they don't tap buttons.
- [x] `routes/chat.py` (SHARED) — accepts JSON **or** multipart now (contract always said both; only form-data was implemented). Errors are proper 4xx/5xx with `{"error": ...}`, never a 200 or a bare crash. Upload size capped at 15MB. A bill photo's OCR text no longer silently overwrites typed text in the same message.

### Dev B — interface & edges
- [x] `index.html` — WhatsApp-style chat UI
- [x] Chat wired to `POST /api/chat`
- [x] Text message round trip works
- [x] `dashboard.html` — stock table
- [x] Dashboard — low stock rows in red
- [~] `asr.py` — rewritten against Sarvam's current API (model name was deprecated, same as Gemini's), keyterms wired to the catalog. **Request shape confirmed live (403 on a bad key, not 400); transcription quality still needs a real key + real audio.**
- [x] Voice input in the UI (mic + file-upload fallback) — untested without a key
- [ ] `ocr.py` — bill photo *(cut first if short on time)*
- [~] `routes/whatsapp.py` — text path done; **media download TODO(Dev B)** *(cut second)*
- [ ] ngrok tunnel live

### Dev B — bugs found in review

Found during a pass over `frontend/*`, `asr.py`, `routes/whatsapp.py`.

**`frontend/app.js` and `dashboard.js` — FIXED by Dev A** (you asked me to, so
we'd both have a working base to start from — I don't normally touch your
files, see `GIT_WORKFLOW.md`):
- [x] Option buttons now send `btn.dataset.value` (`sku:<id>` / `new` / `cancel`), not the label.
- [x] `send()` has an in-flight guard — the send button, mic, and input disable while a request is pending, so double-sends and mid-request taps are no-ops instead of races.
- [x] Errors check `res.ok` and show the real status instead of throwing on `res.json()`.
- [x] `escapeHtml` is now used on `a.sku_name`, `o.label`, `o.value` — no more raw `innerHTML` from catalog text.
- [x] `sender` is now a per-tab id in `sessionStorage`, not a shared `"web-demo"`.
- [x] Mic stream always gets stopped now, even if `MediaRecorder` throws after `getUserMedia` succeeds.
- [x] No-mic-permission click shows a message before opening the file picker.
- [x] `shop_id` is sent now.
- [x] `.slice(0, 14)` removed from the live stock panel — the panel already scrolls (`.side { overflow-y: auto }`), the slice was just hiding items for no reason.
- [x] `dashboard.js` checks `res.ok` on both requests now, same fix as app.js.
- Verified with a headless-browser test (Playwright): ask-once flow end to end, double-click guard, HTML-injection attempt in an item name, mic-permission denial message, dashboard row count. All 10 checks passed. Stock-value formula (`current_qty * cost_per_unit`) left as-is — that's a backend unit-cost question, not a frontend bug, noted inline in the code.

**`asr.py` — FIXED by Dev A, but not yet proven with a real key or a real voice note:**
- [x] MIME is no longer hardcoded — `transcribe()` takes `mime_type` and `chat.py` passes `audio.content_type` through. Falls back to guessing from the filename extension if not given.
- [x] `saarika:v2` was deprecated — checked Sarvam's current docs. The whole Saarika line is gone; it's merged into the Saaras family on the same `/speech-to-text` endpoint. Switched to `model=saaras:v4`. There's also no `language_code` request field anymore (only appears in the response) — removed it.
- [x] Added `mode=translit` for Latin-script output, since that's what the rule extractor and Gemini schema both expect. **Open question, flagged in the code**: Sarvam's docs describe `translit` ("romanization to Latin script") and `codemix` ("code-mixed text output") without fully distinguishing which one actually matches Hinglish speech -> "bees Parle-G aaye". Test both the moment you have a real voice note.
- [x] Added `keyterms` — Sarvam v4 lets you bias recognition toward up to 50 specific terms. Now pulls the shop's own SKU names from the DB and passes them, so "Parle-G" and "Aashirvaad" get a real shot instead of generic ASR.
- [x] If every backend fails, the server log now says which ones were tried and why, not just a silent `None`.
- [x] Whisper gets a prompt hint with the exact Hinglish style and brand names we need — deliberately **not** pinning `language=hi`, since that tends to push Whisper toward Devanagari output, the opposite of what the pipeline expects. The prompt's own Latin script is the more reliable lever for that. Also unverified live — confirm once there's a key.
- **Verified so far**: a deliberately bad key gets a `403` from the real endpoint (not a 400), meaning the request shape itself — model name, mode, keyterms, multipart body — is accepted by Sarvam. Quality (does `translit` actually sound right, does the model mishear anything) still needs a real key + a real voice note. Get the key and send me an audio clip and I'll finish verifying it the same way I did `extract.py`.

**`routes/whatsapp.py`:**
- [ ] Voice notes aren't handled — `MediaUrl0` is never downloaded. This is the headline feature over WhatsApp; it's currently a no-op on audio.
- [ ] `int(NumMedia)` can 500 if Twilio sends something unexpected — guard it.
- [ ] No `X-Twilio-Signature` check (fine for the demo, flag it if anyone asks).
- [ ] The async handler calls `pipeline.handle_message`, which is sync SQLite — blocks the event loop per request. Fine at demo traffic, not production.
- [ ] TwiML replies are text-only — the ask-once options/buttons never reach WhatsApp. Sandbox users have to type the answer in words, which the backend now handles (`new`/`cancel`/free text all work), but make sure the question text itself spells out the choices in words since there are no buttons.
- [ ] Webhook sender is `whatsapp:+91...`, different from the web UI's `web-demo` — the two surfaces don't share pending-question state. Expected, just worth knowing for the demo script.

**`ocr.py`:** not implemented (`NotImplementedError`). First on the cut list — leave it unless everything else is done early.

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
| Plain HTML + hand-written CSS, no React | no build step to break at hour 5 |
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
01:15 — A — fixed bugs from Dev B's review that were on my side: "new"/
         "cancel" had no backend handler (dead end) -- added
         inventory.create_sku() and taught _answer_pending to create-and-book
         or no-op. routes/chat.py now accepts JSON or form, always returns
         proper status codes + {"error"} body, caps uploads at 15MB, doesn't
         let OCR text clobber typed text. Verified live: unknown item -> "new"
         -> SKU created + booked -> same phrase again resolves silently;
         unknown item -> "cancel" -> no stock change. docs/api-contract.md
         updated with the error shape and the new/cancel answer convention.
         Dev B's frontend/asr/whatsapp bugs are listed above for them to fix.
01:45 — A — fixed Dev B's app.js/dashboard.js bugs directly (by request, so
         we'd both have a solid base before Dev B starts). Verified with a
         headless-browser Playwright run, not just reading the code -- 10/10
         checks passed. Added GIT_WORKFLOW.md: no branches, commit to main,
         stick to file ownership, PROGRESS.md is append-only. Read it before
         your next commit.
02:00 — A — asr.py rewritten (by request): saarika:v2 is deprecated, same
         situation gemini-2.0-flash was in -- switched to saaras:v4 on the
         same endpoint, dropped language_code (not an accepted request field
         anymore), added mode=translit and catalog-driven keyterms. Real MIME
         type now flows through from chat.py instead of a hardcoded
         audio/ogg. Verified request shape with a deliberately bad Sarvam
         key -- got a 403 (auth rejected), not a 400 (bad request), so the
         shape itself is accepted. Still need a real SARVAM_API_KEY and an
         actual voice note to verify transcription quality -- ping me with
         both and I'll finish it the way I did extract.py.
```
