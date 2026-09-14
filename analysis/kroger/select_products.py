"""List the priced archive candidates per food, to curate the frozen product list.

  python analysis/kroger/select_products.py            table of every priced candidate
  python analysis/kroger/select_products.py --freeze   write data/kroger/products.json from
                                                       the PICKS below (UPC lists per food)

Baseline rule per product: the capture closest to Feb 27, 2026 with a price, preferring
pre-war (Dec 1 to Feb 26) over early-war (Feb 27 to Mar 13); the store is whichever the
capture priced at and travels with the product.
"""

import argparse
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from units import unit_price_per_lb
import wayback

BASKET = os.path.join(ROOT, "data", "kroger", "basket.json")
PRICES = os.path.join(ROOT, "data", "kroger", "wayback_prices.json")
PRODUCTS = os.path.join(ROOT, "data", "kroger", "products.json")
WAR = 20260227

# Curated picks: food key -> list of slots; each slot is a list of UPCs in preference
# order (the first one with a priced baseline is used). Rule: Kroger label first, then a
# national brand, then one more; plain forms only; premium lines and odd pack forms out.
PICKS = {
    "wheat_bread": [["0001111008450"], ["0007225003712", "0007294561307"], ["0001111008489"]],
    "apples": [["0001111018187"], ["0001111018188"], ["0001111091825"]],
    "carrots": [["0001111091622"], ["0001111091620"]],
    "breaded_chicken": [["0001111015931"], ["0002370006026"], ["0002370006022", "0002370006025"]],
    "tilapia": [["0001111086003"], ["0001111062160"], ["0001111064632"]],
    "peanut_butter": [["0001111009853"], ["0005150024177", "0005150072001"], ["0001111001619"]],
    "broccoli_frozen": [["0001111079549"], ["0001111085669"]],
    "orange_juice": [["0001111014350"], ["0002500004496", "0002500004789"], ["0002500004786"]],
    "tuna": [["0001111083444"], ["0004800000245"], ["0001111089084"]],
    "eggs": [["0001111060903"], ["0001111060933"]],
    "milk_2pct": [["0001111041700"]],
    "drumsticks": [["0001111063825"], ["0024071850000"]],
    "pinto_beans": [["0001111072565"]],
    "pork": [["0025338300000"]],
    "oranges": [["0001111091836"], ["0001111090032"]],
    "corn_canned": [["0001111011383"], ["0002400016302", "0002400003171"], ["0001111011370"]],
    "black_beans": [["0001111072567"], ["0001111089687"]],
}


def best_capture(recs):
    """Prefer pre-war captures, nearest the war start; else the earliest early-war capture."""
    pre = [r for r in recs if int(r["ts"][:8]) < WAR]
    post = [r for r in recs if int(r["ts"][:8]) >= WAR]
    if pre:
        return max(pre, key=lambda r: r["ts"]), False
    return min(post, key=lambda r: r["ts"]), True


def candidates():
    basket = json.load(open(BASKET))
    cache = json.load(open(PRICES))
    pages = [p for p in cache["pages"].values() if p.get("regular") and p.get("location_id") in wayback.STORES]
    out = {}
    for food in basket["foods"]:
        by_upc = {}
        for p in pages:
            if wayback.slug_matches(food, p["slug"], p["upc"]):
                by_upc.setdefault(p["upc"], []).append(p)
        rows = []
        for upc, recs in by_upc.items():
            r, early = best_capture(recs)
            lb = unit_price_per_lb(r["regular"], r.get("size"), food["key"], r.get("sell_by"), r.get("weight_lb"))
            rows.append(dict(upc=upc, name=r.get("name"), brand=r.get("brand"), size=r.get("size"), sell_by=r.get("sell_by"),
                             weight_lb=r.get("weight_lb"), regular=r["regular"], promo=r.get("promo"), ts=r["ts"],
                             early_war=early, location_id=r["location_id"], archive_url=r["archive_url"], price_lb=lb,
                             n_captures=len(recs)))
        rows.sort(key=lambda x: (x["price_lb"] is None, x["price_lb"] or 0))
        out[food["key"]] = (food, rows)
    return out


def show(cands):
    for key, (food, rows) in cands.items():
        print("\n== %s  (%s, %.2f lb/wk)  %d priced candidates" % (food["name"], key, food["lbs_week"], len(rows)))
        for r in rows:
            print("  %s %-58s %-12s %-6s $%6.2f  %s  %s %s  %s" % (
                r["upc"], (r["name"] or "")[:58], (r["size"] or "")[:12], r["sell_by"] or "", r["regular"],
                ("$%.3f/lb" % r["price_lb"]) if r["price_lb"] else "   ?/lb  ", r["ts"][:8],
                "EARLY" if r["early_war"] else "     ", r["location_id"][-3:]))


def freeze(cands):
    basket = json.load(open(BASKET))
    foods = []
    for food in basket["foods"]:
        picks = PICKS.get(food["key"], [])
        _, rows = cands[food["key"]]
        by_upc = {r["upc"]: r for r in rows}
        prods = []
        for slot in picks:
            upc = next((u for u in slot if u in by_upc), None)
            if upc is None:
                print("  ! %s: no priced baseline for any of %s" % (food["key"], slot))
                continue
            r = by_upc[upc]
            prods.append(dict(upc=upc, name=r["name"], brand=r["brand"], size=r["size"], sell_by=r["sell_by"],
                              weight_lb=r["weight_lb"], location_id=r["location_id"],
                              baseline=dict(regular=r["regular"], promo=r["promo"], ts=r["ts"], early_war=r["early_war"],
                                            archive_url=r["archive_url"])))
        foods.append(dict(key=food["key"], name=food["name"], lbs_week=food["lbs_week"], tfp_share=food["tfp_share"],
                          unit=food["unit"], products=prods))
    out = dict(frozen_on=date.today().isoformat(), stores=wayback.STORES, store={"location_id": "02900310", "name": wayback.STORES["02900310"]},
               rule="Up to three products per food: Kroger label, a national brand, one more; regular shelf price; same UPC at both dates, at the store the baseline was archived from",
               foods=foods)
    json.dump(out, open(PRODUCTS, "w"), indent=1)
    n = sum(len(f["products"]) for f in foods)
    print("wrote %s: %d foods with products, %d products" % (PRODUCTS, sum(1 for f in foods if f["products"]), n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    c = candidates()
    if a.freeze:
        freeze(c)
    else:
        show(c)


if __name__ == "__main__":
    sys.exit(main())
