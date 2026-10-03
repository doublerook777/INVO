"""Hinglish reply strings.

Keep replies short and in Latin-script Hinglish. "20 Parle-G add ho gaye" beats
"20 units of Parle-G have been added to inventory." Judges notice the difference.

Dev A owns this file.
"""


def _fmt(n):
    return str(int(n)) if float(n) == int(n) else f"{float(n):.2f}".rstrip("0").rstrip(".")


def confirm(actions):
    if not actions:
        return "Samajh nahi aaya. Dobara bhejiye?"
    parts = [f"{_fmt(a['qty'])} {a['unit']} {a['sku_name']}" for a in actions]
    joined = ", ".join(parts[:-1]) + (" aur " + parts[-1] if len(parts) > 1 else parts[0])
    verb = "add ho gaye" if actions[0]["type"] == "stock_in" else "kam ho gaye"
    line = f"Theek hai! {joined} {verb}."

    priced = [a for a in actions if a.get("cost_per_unit")]
    if priced:
        a = priced[0]
        line += f"\n{a['sku_name']} ka rate ₹{a['cost_per_unit'] / 100:.0f} save kar liya."
    if any(not a.get("unit_confident", True) for a in actions):
        line += "\n(Unit pakka nahi tha -- check kar lijiye.)"
    return line


def ask_which(raw_name, candidates):
    opts = " ya ".join(c["name"] for c in candidates[:2])
    return f"{raw_name.title()} ka matlab {opts}?"


def offer_new(raw_name):
    return f"'{raw_name.title()}' naya item lagta hai. Add kar doon?"


def not_understood():
    return "Samajh nahi aaya. Jaise bolein: \"bees Parle-G aaye\""
