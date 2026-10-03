"""Unit conversion.

Read this before you touch quantities. If a 'peti' gets written to the ledger as
1 instead of 24, every profit number downstream is silently wrong and nobody
notices until the judge asks.

Dev A owns this file.
"""

# Multipliers into a base unit. 'peti' etc. are ambiguous across items, so the
# per-SKU override below wins when it exists.
GENERIC = {
    # count
    "packet": 1.0, "pkt": 1.0, "piece": 1.0, "pc": 1.0, "nos": 1.0, "adad": 1.0,
    "dozen": 12.0, "darjan": 12.0,
    "peti": 24.0, "crate": 24.0, "carton": 24.0, "box": 24.0,
    # weight -> kg
    "kg": 1.0, "kilo": 1.0, "kilogram": 1.0,
    "gram": 0.001, "g": 0.001, "gm": 0.001,
    "pav": 0.25, "paav": 0.25,      # quarter kilo
    "adha": 0.5, "aadha": 0.5,      # half kilo
    "bori": 50.0, "bora": 50.0,     # sack
    "quintal": 100.0,
    # volume -> litre
    "litre": 1.0, "liter": 1.0, "l": 1.0, "ltr": 1.0,
    "ml": 0.001,
}

# When a shop says "peti" they mean something different for Maggi than for Coke.
# Keyed by sku name (lowercased substring match), then unit.
PER_SKU = {
    "parle-g": {"peti": 48.0},
    "maggi":   {"peti": 96.0},
    "coca-cola": {"crate": 24.0, "peti": 24.0},
}

ALIASES = {
    "kilos": "kg", "kgs": "kg", "grams": "gram", "packets": "packet",
    "pieces": "piece", "dozens": "dozen", "petis": "peti", "boris": "bori",
    "litres": "litre", "liters": "litre",
}


def normalize_unit(unit):
    if not unit:
        return ""
    u = unit.strip().lower()
    return ALIASES.get(u, u)


def to_canonical(qty, raw_unit, canonical_unit, sku_name=""):
    """Convert `qty raw_unit` into the SKU's canonical unit.

    Returns (converted_qty, confident). When `confident` is False the caller
    should ask the user rather than guess -- a wrong conversion is worse than
    a question.
    """
    raw = normalize_unit(raw_unit)
    canon = normalize_unit(canonical_unit)

    if not raw or raw == canon:
        return float(qty), True

    name = (sku_name or "").lower()
    for key, overrides in PER_SKU.items():
        if key in name and raw in overrides:
            return float(qty) * overrides[raw] / GENERIC.get(canon, 1.0), True

    if raw in GENERIC and canon in GENERIC:
        return float(qty) * GENERIC[raw] / GENERIC[canon], True

    # Unknown unit. Pass it through but flag it so the caller can ask.
    return float(qty), False
