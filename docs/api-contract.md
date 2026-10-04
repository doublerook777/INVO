# API contract

**Frozen after initial setup.** From here, no field renames without telling the other dev.

Base URL: `http://localhost:8000`

Dev A implements these. Dev B codes against them. Until the real logic exists,
these endpoints return correctly-shaped stub data, so **Dev B is never blocked.**

---

## `POST /api/chat`

The one entry point. WhatsApp, the web UI, and curl all come through here.

### Request

`multipart/form-data` (so audio and images can ride along) or JSON if text-only.

| Field | Type | Required | Notes |
|---|---|---|---|
| `shop_id` | int | yes | `1` for the demo shop |
| `sender` | string | yes | phone number or `web-demo` |
| `text` | string | no | the message, if typed |
| `audio` | file | no | voice note |
| `image` | file | no | photo of a supplier bill |

At least one of `text` / `audio` / `image` must be present.

### Response

```json
{
  "reply": "Theek hai! 20 Parle-G packet aur 5 kg Atta add ho gaye.",
  "transcript": "aaj bees Parle-G aaye, aur paanch kilo aata",
  "needs_answer": false,
  "actions": [
    {
      "type": "stock_in",
      "sku_id": 3,
      "sku_name": "Parle-G Biscuit",
      "qty": 20,
      "unit": "packet",
      "qty_canonical": 20,
      "cost_per_unit": 1000
    }
  ],
  "debug": { "intent": "stock_in", "matched_via": "alias" }
}
```

| Field | Meaning |
|---|---|
| `reply` | the Hinglish text to show in the chat bubble |
| `transcript` | what we heard, if audio. `null` for text messages. Show it greyed above the bubble — showing the ASR output builds trust |
| `needs_answer` | `true` when the bot asked a clarifying question. Dev B: render the `options` as tappable buttons |
| `actions` | what actually changed. Dev B can render these as a little receipt card |
| `debug` | never shown to the user; handy during the demo |

### When the bot needs to ask (the money shot)

```json
{
  "reply": "Parle-G ka matlab Parle-G Biscuit ya Parle Monaco?",
  "transcript": "das parle aaye",
  "needs_answer": true,
  "options": [
    { "label": "Parle-G Biscuit", "value": "sku:3" },
    { "label": "Parle Monaco",    "value": "sku:7" },
    { "label": "Naya item hai",   "value": "new" }
  ],
  "actions": []
}
```

The user's next `POST /api/chat` just sends the chosen `value` as `text`. The
backend knows what's pending via the `pending_asks` table — Dev B doesn't have to
track any state.

**After this, the alias is saved and the bot never asks again.** Make sure the
demo shows a second message with the same wording going straight through.

**Answering "new" / "cancel":** if the user picks "Naya item hai" or "Nahi" (or
WhatsApp-types "haan"/"nahi" since the sandbox has no tappable buttons), send
`new` or `cancel` as `text` — same as any other answer. `new` creates a SKU from
the original raw item and books the movement against it; `cancel` drops the
pending question with no side effect.

### Errors

Any failure is a non-2xx status with `{"error": "<message>"}` — never a 200
with an error field, and never a bare 500 with no body (the frontend's
`res.json()` would throw on that).

| Status | When |
|---|---|
| 400 | bad body, or none of `text`/`audio`/`image` present |
| 413 | uploaded file over 15MB |
| 500 | the pipeline threw — check the server log, the response body won't have detail |

---

## `GET /api/inventory?shop_id=1`

```json
{
  "shop": { "id": 1, "name": "Sharma Kirana Store" },
  "items": [
    {
      "sku_id": 3,
      "name": "Parle-G Biscuit",
      "current_qty": 12,
      "unit": "packet",
      "cost_per_unit": 1000,
      "sell_price": 1200,
      "avg_daily_sales": 4.2,
      "days_of_cover": 2.9,
      "status": "low"
    }
  ]
}
```

`status` is one of `ok` | `low` | `out`. Dev B: colour the row off this field
alone, don't recompute thresholds in the frontend.

---

## `GET /api/alerts?shop_id=1`

Everything that needs reordering, worst first.

```json
{
  "alerts": [
    {
      "sku_id": 3,
      "name": "Parle-G Biscuit",
      "days_of_cover": 2.9,
      "suggested_order_qty": 40,
      "unit": "packet",
      "message": "Parle-G 3 din mein khatam ho jayega. 40 packet order bhej doon?"
    }
  ]
}
```

---

## `POST /api/whatsapp/webhook`

Twilio posts here. Dev B owns it. It translates Twilio's form fields into a call
to the same `handle_message()` the web UI uses, then returns TwiML.

**It must not contain any business logic.** If you're tempted to put an `if`
statement about inventory in this file, it belongs in `pipeline.py`.

---

## Errors

Every endpoint, on failure:

```json
{ "error": "human readable thing that went wrong" }
```

with a 4xx/5xx status. Dev B: show `error` in a grey bubble rather than failing
silently — during the demo we need to see what broke.
