# Demo script — the three screenshots

Run `python -m app.seed --reset` first, so the shop is clean and the numbers
look the same every time. Then open `index.html` and type these in order.

## Screenshot 1 — the hero shot

Type (or send as a voice note):

> aaj bees Parle-G aaye, aur paanch kilo aata, aata ka rate badh gaya - chhiyalis rupaye

The bot books **two different items with two different units from one sentence**,
and picks up the new atta rate. Capture the chat bubble **and** the stock panel
beside it, so the judge sees the table move.

## Screenshot 2 — the money shot (ask once, then remember)

Three messages, one after the other:

1. `do amul aaye`
   → *"Amul ka matlab Amul Butter 100g ya Amul Taaza Milk 500ml?"* with buttons
2. tap **Amul Taaza Milk 500ml**
   → *"2 packet Amul Taaza Milk 500ml add ho gaye. Ab se 'amul' yaad rahega."*
3. `paanch amul aaye`
   → books it straight away, **no question**

Capture all three in one frame. This is the slide that separates us from a
ChatGPT wrapper: the system got *less annoying* because it learned this shop's
vocabulary.

## Screenshot 3 — it speaks first

Open `dashboard.html`. Five items are already low from the seeded history.
Capture the red rows plus the "Reorder now" panel with the Hinglish nudge:

> Bread 1 din mein khatam ho jayega. 76 packet order bhej doon?

---

## If a judge asks

**"Why not just an app?"**
A shopkeeper has a customer in front of them. Typing into an app takes two
minutes; a voice note takes fifteen seconds. They already send voice notes all
day. We removed the behaviour change, not just the friction.

**"How accurate is the speech recognition?"**
Be honest — say what you measured, on how many clips, and name the failure mode
(a noisy shop). Don't claim a number you didn't test.

**"What if it gets something wrong?"**
Show the correction path. Then point out the near-tie rule: when two items score
the same, we *ask* instead of guessing, because silently booking stock against
the wrong item is the worst thing this product could do.

**"Is this really AI or just if-statements?"**
Both, deliberately. The LLM handles the messy part — understanding Hinglish
speech. The reorder prediction is a days-of-cover average, not a model, because
a model trained on two weeks of one shop's data would be worse and we'd be
lying about it.

## Backup

**Record a video of all three flows before you present.** Venue wifi fails, and
a dead demo costs more than the ten minutes this takes.
