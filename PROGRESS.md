# Progress

**Both devs: update this file as you finish things.** We're both using AI agents
that will run out of context. When a new session starts, this file is the handoff.

How to use it: tick the boxes, and append a one-line entry to the log at the
bottom with the time. Don't write essays — the next agent needs facts, not prose.

---

## Status at a glance

| | Dev A (Ayush) — backend brain | Dev B — interface & edges |
|---|---|---|
| Current task | Backend + ASR fully verified live. Demo plan: web UI for all 3 screenshots (Twilio trial blocks replies) | `ocr.py` next (`whatsapp.py` done, blocked on Twilio account tier, not code) |
| Blocked on | nothing | nothing code-side; WhatsApp demo blocked on Twilio trial restrictions |
| Last commit | Capped Gemini timeout at 8s, replied on Twilio in PROGRESS.md | whatsapp.py: voice notes + TwiML content-type |

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
- **Real voice notes, end to end** — a real WhatsApp-style voice note
  ("paanch amul aaye") uploaded to `/api/chat` transcribes correctly via
  Sarvam and resolves/books correctly. **Screenshot 1 can be shot with a real
  voice note now, not a typed message.**

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
- [x] **Confirmed API key leak, fixed.** `extract.py` sent the Gemini key as `?key=...`. A failed call's error text (and the log line around it) included the full URL with the key in plain text — a fake-key test is exactly how it got caught. Moved to the `x-goog-api-key` header. Verified: a deliberately bad key's error message no longer contains any part of the key, checked programmatically.
- [x] **`pipeline.py` rewritten** to fix a cluster of related bugs, most found by Dev B's second review:
  - `"haan"` after a disambiguation question (`"Butter ya Milk?"`) used to match the same loose-synonym list as the real "create new" offer, silently creating a junk SKU and aliasing it forever. The loose synonyms (`haan`/`yes`/`ha`) now only apply when there are **no candidates** to confuse them with — the literal `"new"` value (what the actual button sends) still works everywhere, including the escape-hatch option on a disambiguation question.
  - A message sent while a question was pending used to be swallowed if it didn't look like a valid answer — now `_answer_pending` returns `None` for "not an answer", and `handle_message` falls through to processing it as a brand-new message instead of discarding it.
  - An empty/whitespace-only answer used to silently match the *first* candidate (`"" in any_string` is always `True` in Python). Guarded.
  - `sku:abc` used to raise an uncaught `ValueError`. Caught, treated as "not an answer" (falls through, doesn't crash).
  - Items after an ambiguous one in the same message used to be silently dropped once the loop hit a question and `break`ed. The pending row now carries the remaining items and the actions already booked; answering the question resumes processing the rest, chaining through multiple questions in one message if needed.
  - A query (`"kitna stock bacha hai"`) or any non-movement intent could still carry a parsed item from a bad parse (`"2 kg aata chahiye"` → "I need 2kg atta" parsed an item) and got silently booked as stock-in regardless. Gated: only `stock_in`/`stock_out` intents ever reach the resolver now; a real `query` intent gets an honest reply pointing at the dashboard instead of "samajh nahi aaya".
  - `unit_confident=False` used to be purely cosmetic — a footnote in the reply, while the write happened anyway with a possibly-wrong conversion. `units.py`'s own docstring already said "the caller should ask the user rather than guess"; nobody had implemented that part. Now it does: an unrecognized unit asks for confirmation before writing anything, reusing the same pending-ask machinery as SKU disambiguation.
  - `extract()` now tags its own output `_source: "llm"|"rule"` and pipeline surfaces it in `debug.extract_source` — so a silent fallback to rules (e.g. hitting the Gemini quota again) is visible in the API response, not just a log line you have to be watching for.
- [x] **Three more bugs from Dev B's third pass on `_answer_pending`, all confirmed and fixed:**
  - A pending row saved by an older build (different payload shape) raised `KeyError` on `payload["reason"]`, and since that happened *before* the row was cleared, every subsequent message from that sender hit the same crash forever. Fixed: clear the row first, parse the payload in a `try/except`, and treat anything unreadable as "not an answer" instead of crashing.
  - `cancel` used to drop the rest of the message, not just the item being asked about — `"do amul aaye aur das maggi aaye"` then `"cancel"` never booked the Maggi. Fixed: cancel now continues processing the remaining items, with a note naming the specific item that was skipped.
  - Abandoning a question (sending something that isn't an answer to it) left already-booked actions from earlier in that message with no confirmation — the write happened, the user just never heard about it. Fixed: `_answer_pending` now returns `(result, abandoned_actions)`, and `handle_message` folds any abandoned actions' confirmation into whatever the fresh message turns into next.
  - All three verified against the real running server: a hand-inserted old-schema row no longer 500s (confirmed the sender's *next* message works too, not just that it doesn't crash); the cancel-with-remaining-items case correctly booked Maggi and left Amul's ledger untouched (checked directly); the abandoned-question case correctly re-surfaced the Parle-G confirmation in the next reply. Re-ran the original 3 demo sentences and the full Playwright suite — still all green.
- [x] `resolver.py` — **fuzzy auto-accept no longer writes a permanent alias.** It was never confirmed by a human; auto-accepting it each time is fine, silently cementing an unconfirmed guess as a permanent mapping is how one slightly-off match becomes permanently wrong. Aliases are now only written when a human actually answers a clarifying question, or names an item by creating it.
- [x] `inventory.py` — **`apply_movement` is now atomic.** It was 2-3 separate `db.execute()` calls (each its own connection + commit); a crash between them could leave the ledger and the SKU's `current_qty` out of sync. Now one connection, one commit.
- [x] `routes/chat.py` — **unknown `shop_id` is now a clean 400**, validated at the boundary, instead of failing deep inside `create_sku` on a foreign-key violation and surfacing as a 500.
- [x] `routes/chat.py` — **the blocking-event-loop bug.** `pipeline.handle_message` is sync (sqlite3 + a sync Gemini call with a 15s timeout) called directly inside an async route — one slow call used to stall every other request. Wrapped in `starlette.concurrency.run_in_threadpool` instead of rewriting the sync core as async.

### Dev B — interface & edges
- [x] `index.html` — WhatsApp-style chat UI
- [x] Chat wired to `POST /api/chat`
- [x] Text message round trip works
- [x] `dashboard.html` — stock table
- [x] Dashboard — low stock rows in red
- [x] `asr.py` — rewritten against Sarvam's current API (model name was deprecated, same as Gemini's), keyterms wired to the catalog. **Fully verified live**: two real voice notes ("paanch amul aaye", "das maggi bik gaye") transcribed perfectly, through the actual `/api/chat` voice upload path end to end (transcribe → Gemini extract → resolve → ledger write). `mode=translit` confirmed correct, no longer a guess.
- [x] Voice input in the UI (mic + file-upload fallback) — untested without a key
- [ ] `ocr.py` — bill photo *(cut first if short on time)*
- [~] `routes/whatsapp.py` — text + voice-note path coded and tested locally; **real WhatsApp replies BLOCKED by the Twilio trial account, see Known issues** *(cut second)*
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

**`asr.py` — FIXED and FULLY VERIFIED LIVE:**
- [x] MIME is no longer hardcoded — `transcribe()` takes `mime_type` and `chat.py` passes `audio.content_type` through. Falls back to guessing from the filename extension if not given.
- [x] `saarika:v2` was deprecated — checked Sarvam's current docs. The whole Saarika line is gone; it's merged into the Saaras family on the same `/speech-to-text` endpoint. Switched to `model=saaras:v4`. There's also no `language_code` request field anymore (only appears in the response) — removed it.
- [x] `mode=translit` for Latin-script output — **confirmed correct, not a guess anymore.** Tested against two real voice notes: "paanch amul aaye" and "das maggi bik gaye", both transcribed back **verbatim correct**, through the real `/api/chat` voice path end to end (Sarvam transcribe → Gemini extract → resolver → ledger write). Maggi's "bik gaye" even correctly produced a `stock_out` with the ledger decremented.
- [x] Added `keyterms` — Sarvam v4 lets you bias recognition toward up to 50 specific terms. Pulls the shop's own SKU names from the DB and passes them, so "Parle-G" and "Aashirvaad" get a real shot instead of generic ASR.
- [x] If every backend fails, the server log now says which ones were tried and why, not just a silent `None`.
- [x] Whisper gets a prompt hint with the exact Hinglish style and brand names we need — deliberately **not** pinning `language=hi`, since that tends to push Whisper toward Devanagari output, the opposite of what the pipeline expects. Whisper itself is still unverified (no `OPENAI_API_KEY` tested) — low priority, Sarvam is the primary path and it works.

**`routes/whatsapp.py`:**
- [x] Voice notes aren't handled — `MediaUrl0` is never downloaded. This is the headline feature over WhatsApp; it's currently a no-op on audio.
- [x] `int(NumMedia)` can 500 if Twilio sends something unexpected — guard it.
- [ ] No `X-Twilio-Signature` check (fine for the demo, flag it if anyone asks).
- [x] The async handler calls `pipeline.handle_message`, which is sync SQLite — blocks the event loop per request. Fine at demo traffic, not production.
- [x] TwiML replies are text-only — the ask-once options/buttons never reach WhatsApp. Sandbox users have to type the answer in words, which the backend now handles (`new`/`cancel`/free text all work), but make sure the question text itself spells out the choices in words since there are no buttons.
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
| **Twilio trial ("Try out WhatsApp", +1 737 250 8034) never delivers the bot's reply.** Inbound reaches us fine (ngrok + backend log show Twilio's POST, we return valid TwiML `text/xml`, HTTP 200), but nothing outbound appears in Twilio's Message Logs or on the phone. Twilio logs error 12300 on the inbound messages. Direct API send fails with `ContentSid Required`; creating our own template via Content API fails with code 20003 "not available on a Trial account"; the Send tab only offers the sample "Appointment Reminders" template; Monitor/Alerts API also trial-locked so no error detail. Not proven that TwiML replies are blocked, but every sign points to the trial allowing only the sample template | **Use the web chat UI for the demo** (roadmap cut list: "real Twilio -- web UI screenshots identically"). `whatsapp.py` is complete and should work unchanged once the account is upgraded. Dev A: worth a second pair of eyes -- if you have a different Twilio account/number (paid, or the classic +1 415 523 8886 sandbox), point it at the webhook (ngrok http 8000, POST /api/whatsapp/webhook) and see if replies arrive |
| Gemini extraction takes **4-11 s per message, occasionally 20s+** on `gemini-3.1-flash-lite` | **Confirmed not a thinkingBudget problem** -- this model never reports `thoughtsTokenCount` regardless of `thinkingConfig`, it just doesn't do extended thinking. The latency is the model's own generation time on the free tier. Capped `extract.py`'s timeout at 8s so a slow call fails over to the rule-based extractor (proven-correct on every demo sentence) instead of visibly hanging |
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
02:30 — A — second review pass from Dev B turned up a confirmed key leak
         (Gemini key in ?key=... ended up in error text and logs -- moved to
         a header) plus 9 more real bugs, mostly in pipeline.py: "haan"
         creating junk SKUs on the wrong question, swallowed messages when
         an answer didn't match, an empty answer matching the first
         candidate, sku:abc crashing, items after a question getting
         dropped, queries silently booking stock, fuzzy matches permanently
         (and unconfirmed-ly) aliasing themselves, unit_confident being
         purely cosmetic, non-atomic writes, a bad shop_id 500ing, and the
         sync Gemini call blocking the whole event loop. All fixed and
         re-verified: the original 3 demo sentences still pass unchanged,
         plus a dedicated test for each bug (multi-item continuation, the
         unit-confirmation ask, the haan/candidates fix, sku:abc, empty
         answers, query-vs-booking, bad shop_id). Re-ran the Playwright
         frontend suite too -- still 10/10, no contract regression from the
         pipeline rewrite.
02:45 — A — Dev B's third pass on _answer_pending found 3 more real bugs, all
         fixed: a stale pending row from an older schema crashed that sender
         forever (payload parsed before clearing, so the row never got
         removed); cancel dropped the rest of the message instead of just
         the one item being asked about; abandoning a question lost the
         confirmation for whatever was already booked earlier in that
         message (the write still happened, the user just never heard
         about it). _answer_pending now returns (result, abandoned_actions)
         so the caller can fold a lost confirmation into whatever comes
         next. Verified each with the real server: old-schema row no longer
         wedges the sender, cancel correctly books the item after the one
         skipped, abandoned question correctly re-confirms what was booked.
         Next: Sarvam key + a real voice note to finish verifying asr.py.
03:00 — A — SARVAM_API_KEY landed, plus two real voice notes ("paanch amul
         aaye", "das maggi bik gaye"). Both transcribed verbatim-correct via
         Sarvam's saaras:v4/mode=translit. Ran them through the real
         /api/chat voice upload path end to end: Maggi correctly resolved
         via alias, direction correctly read as stock_out from "bik gaye",
         ledger decremented. Amul correctly asked for disambiguation (fresh
         DB, no learned alias yet). asr.py is DONE -- no longer a guess on
         translit vs codemix, confirmed with real audio. Screenshot 1 can
         now be shot with an actual voice note instead of typed text.
03:00 — B — whatsapp.py: voice notes now work end to end in code. Downloads
         MediaUrl0 with Twilio basic auth (redirect to CDN, 15MB cap), passes
         real content type to asr.transcribe, runs pipeline in a threadpool,
         guards NumMedia, echoes the transcript, and appends the typable
         answer words (names / new / nahi / haan) to ask-once questions since
         WhatsApp has no buttons. Tested locally: mocked Twilio form posts,
         and the media fetch against a local auth+redirect server. NOT tested
         against real Twilio/ngrok yet. Signature check still skipped.
03:45 — B — Tried real WhatsApp via Twilio sandbox + ngrok (static domain). Text
         and voice reach the backend and are processed (log + ngrok inspector
         confirm), but the reply never reaches the phone: trial account only
         allows the sample template (ContentSid Required on REST send, Content
         API and Monitor API both trial-locked, no error text available).
         Details + what to try in Known issues. whatsapp.py also now returns
         text/xml (Twilio's documented TwiML type); harmless, did not fix it.
         ngrok stopped. Falling back to web UI for Screenshots 1-3, then ocr.py.
04:00 — A — Agreed: web UI for all 3 screenshots, whatsapp.py's diagnosis
         sounds right and isn't worth more time chasing. I don't have a
         different Twilio account/number to test with either, so can't
         independently confirm it -- but ContentSid Required + Content/Monitor
         API both trial-locked is a well-known trial-tier wall, not something
         our code is doing wrong. whatsapp.py is solid work either way, ready
         for whenever the account gets upgraded.
         Also checked your Gemini latency flag -- real, reproduced it myself
         (4-11s typical, one 28s outlier). Not a thinkingBudget problem:
         measured thoughtsTokenCount on gemini-3.1-flash-lite and it's always
         None regardless of thinkingConfig -- this model doesn't do extended
         thinking at all, the latency is just its own generation time on the
         free tier. Lowered extract.py's timeout 15s -> 8s so a slow call
         fails over to the rule-based extractor (proven-correct on every
         demo sentence) instead of visibly hanging. Verified: same request
         now returns in ~8.4s with extract_source: "rule", identical correct
         output. No faster model with decent free quota that I know of right
         now -- this is the accepted tradeoff for using gemini-3.1-flash-lite.
```
