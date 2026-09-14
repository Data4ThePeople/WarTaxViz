"""Turn a Kroger size string ("40 oz", "1 gal", "12 ct", "59 fl oz", "5 lb") into pounds,
so every product's price can be expressed per pound of the basket food."""

import re

LB_PER_GALLON_MILK = 8.6
LB_PER_FL_OZ_JUICE = 8.7 / 128.0   # orange juice / soy milk, ~1.04 g/mL
LB_PER_DOZEN_LARGE_EGGS = 1.5

# per-food overrides for count-based or volume-based sizes
FOOD_RULES = {
    "eggs": {"ct": LB_PER_DOZEN_LARGE_EGGS / 12.0},
    "milk_1pct": {"gal": LB_PER_GALLON_MILK}, "milk_skim": {"gal": LB_PER_GALLON_MILK},
    "milk_2pct": {"gal": LB_PER_GALLON_MILK}, "milk_whole": {"gal": LB_PER_GALLON_MILK},
    "orange_juice": {"fl oz": LB_PER_FL_OZ_JUICE}, "soy_milk": {"fl oz": LB_PER_FL_OZ_JUICE},
}
GAL_FL_OZ = {"gal": 128.0, "qt": 32.0, "pt": 16.0, "fl oz": 1.0, "l": 33.814, "ml": 0.033814}


def size_to_lbs(size, food_key, weight_lb=None):
    """Pounds in one retail unit, or None if the size cannot be resolved."""
    if not size:
        return weight_lb
    s = size.lower().replace("fl. oz", "fl oz").replace("fluid ounce", "fl oz").strip()
    rules = FOOD_RULES.get(food_key, {})
    # "2 x 12 oz", "12 ct / 6 oz" -> take the first quantity and unit pair
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(fl oz|oz|lb|lbs|gal|qt|pt|ct|count|each|ea|l|ml)\b", s)
    if not m:
        return weight_lb
    qty, unit = float(m.group(1)), m.group(2)
    if unit in ("lb", "lbs"):
        return qty
    if unit == "oz":
        return qty / 16.0
    if unit in ("fl oz", "gal", "qt", "pt", "l", "ml"):
        fl = qty * GAL_FL_OZ[unit]
        if "gal" in rules:
            return fl / 128.0 * rules["gal"]
        if "fl oz" in rules:
            return fl * rules["fl oz"]
        return fl * (8.34 / 128.0)   # water-like density as a fallback
    if unit in ("ct", "count"):
        if "ct" in rules:
            return qty * rules["ct"]
        return weight_lb
    if unit in ("each", "ea"):
        return weight_lb
    return weight_lb


def unit_price_per_lb(regular, size, food_key, sell_by=None, weight_lb=None):
    """Price per pound for a product. Sold-by-weight items are already $/lb.

    Kroger's page weight is the net weight for packaged goods but a 1.0 placeholder for
    loose produce sold by the each, so a bare "1 each" / "1 ct" with weight 1.0 is
    treated as unknown rather than priced at $/lb."""
    if regular is None:
        return None
    if sell_by and sell_by.upper() == "WEIGHT":
        return regular
    s = (size or "").lower().strip()
    bare_unit = re.fullmatch(r"1\s*(each|ea|ct|count|lb|lbs?)", s) is not None or s == ""
    if bare_unit:
        if weight_lb and abs(weight_lb - 1.0) > 1e-6:
            return regular / weight_lb   # real net weight overrides a nominal "1 lb" / "1 each"
        if s.endswith(("each", "ea", "ct", "count")) or s == "":
            return None
    lbs = size_to_lbs(size, food_key, weight_lb)
    if not lbs:
        return None
    return regular / lbs
