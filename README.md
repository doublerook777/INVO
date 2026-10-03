# StockSaathi

**A WhatsApp agent that keeps a kirana shop's stock register, by voice.**

HackSprint 2026 — Track 1 (FinTech & Smart Commerce)

---

## The one-line pitch

Shop owners already send voice notes all day. We just listen to them and keep the stock register for them.

## The problem

Small shop owners don't use inventory apps. Not because the apps are bad — because
typing is impossible when you have a customer in front of you. Every inventory app
dies at the same place: data entry.

## What we built

The owner sends a WhatsApp voice note:

> "aaj bees Parle-G aaye, aur paanch kilo aata, aata ka rate badh gaya — chhiyalis rupaye"

The bot understands it, updates stock, and replies with a confirmation. No app, no
typing, no training. And before stock runs out, the bot messages *first*:

> Parle-G 3 din mein khatam ho jayega. Order bhej doon?

## Why it's hard (the actual technical problem)

Not the plumbing — the **item names**. One shop calls it `parle g`, `parle-g`,
`chhota parle`, `पारले जी`. Units are chaos: packet, peti, crate, dozen, kg, pav, bori.
The bot has to resolve messy speech to the right SKU, ask **once** when unsure, then
never ask again.

## Quick start

See [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) for full setup.

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env     # add your API keys
python -m app.seed          # creates demo shop + 2 weeks of history
uvicorn app.main:app --reload --port 8000

# frontend  (separate terminal, no build step, no npm)
cd frontend && python3 -m http.server 5500
# open http://localhost:5500
```

## Docs

| File | What's in it |
|---|---|
| [`ROADMAP.md`](./ROADMAP.md) | 6-hour plan, hour by hour, who does what |
| [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) | Architecture, file structure, tools, setup |
| [`PROGRESS.md`](./PROGRESS.md) | Live status. **Update this as you work.** |
| [`docs/api-contract.md`](./docs/api-contract.md) | Frozen API shapes — read before coding |

## Team

| | Owner |
|---|---|
| Dev A — backend brain | Ayush |
| Dev B — interface & edges | (teammate) |
