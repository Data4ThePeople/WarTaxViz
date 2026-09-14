"""Price the fixed TFP basket at Kroger before the war and now, and write the report.

Inputs
  data/kroger/basket.json            foods and TFP pounds/week
  data/kroger/products.json          frozen products per food, with the pre-war baseline
  data/kroger/snapshots/<latest>.json current regular prices (Kroger API), or a file
                                     passed with --now in the same shape
  site/data.json                     CPI food numbers for the side-by-side
Output
  writeups/kroger-basket-test.md

Run:  python analysis/kroger/compare.py [--now data/kroger/snapshots/2026-09-14.json]
"""

import argparse
import glob
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.expanduser("~/.claude/d4tp-process/.env"))

import fetch_bls
from constants import CEX_FOOD_AT_HOME_ANNUAL, WAR_START
import food_kroger  # pipeline/food_kroger.py

BASKET = os.path.join(ROOT, "data", "kroger", "basket.json")
PRODUCTS = os.path.join(ROOT, "data", "kroger", "products.json")
SNAPSHOTS = os.path.join(ROOT, "data", "kroger", "snapshots")
SITE_DATA = os.path.join(ROOT, "site", "data.json")
OUT = os.path.join(ROOT, "writeups", "kroger-basket-test.md")

# BLS average-price series that match basket foods (national, monthly, unadjusted)
BLS_MATCH = {
    "wheat_bread": ("APU0000702212", "Bread, whole wheat, per lb"),
    "white_bread": ("APU0000702111", "Bread, white, per lb"),
    "apples": ("APU0000711111", "Apples, Red Delicious, per lb"),
    "carrots": ("APU0000712403", "Carrots, per lb"),
    "milk_whole": ("APU0000709112", "Milk, whole, per gal"),
    "milk_2pct": ("APU0000FJ1101", "Milk, low-fat/reduced/skim, per gal"),
    "potatoes": ("APU0000712112", "Potatoes, white, per lb"),
    "peanut_butter": ("APU0000716141", "Peanut butter, creamy, per lb"),
    "broccoli_frozen": ("APU0000712412", "Broccoli, per lb (fresh)"),
    "tuna": ("APU0000707111", "Tuna, light, chunk, per lb"),
    "bananas": ("APU0000711211", "Bananas, per lb"),
    "eggs": ("APU0000708111", "Eggs, grade A large, per doz"),
    "tomatoes": ("APU0000712311", "Tomatoes, field grown, per lb"),
    "drumsticks": ("APU0000706212", "Chicken legs, bone-in, per lb"),
    "lettuce": ("APU0000712211", "Lettuce, iceberg, per lb"),
    "pinto_beans": ("APU0000714233", "Beans, dried, per lb"),
    "pork": ("APU0000FD4101", "All other pork, per lb"),
    "oranges": ("APU0000711311", "Oranges, navel, per lb"),
    "cucumbers": ("APU0000712409", "Cucumbers, per lb"),
    "corn_canned": ("APU0000714221", "Corn, canned, per lb"),
    "chicken_breast": ("APU0000FF1101", "Chicken breast, boneless, per lb"),
    "greek_yogurt": ("APU0000FJ4101", "Yogurt, per 8 oz"),
    "rice_white": ("APU0000701312", "Rice, white long grain, per lb"),
}


def months_between(d0, d1):
    return (d1.year - d0.year) * 12 + (d1.month - d0.month) + (d1.day - d0.day) / 30.4


def load_now(path):
    if path is None:
        files = sorted(glob.glob(os.path.join(SNAPSHOTS, "*.json")))
        if not files:
            sys.exit("no snapshot in data/kroger/snapshots; run fetch_kroger.py or pass --now")
        path = files[-1]
    return json.load(open(path)), path


def fmt_pct(x):
    return ("+" if x >= 0 else "−") + "%.1f%%" % abs(x * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now")
    a = ap.parse_args()
    basket = json.load(open(BASKET))
    products = json.load(open(PRODUCTS))
    now, now_path = load_now(a.now)
    now_prices = now["prices"]
    now_date = date.fromisoformat(now["date"])
    site = json.load(open(SITE_DATA))
    prod_by_key = {f["key"]: f for f in products["foods"]}

    # products.json carries lbs_week and tfp_share per food (copied from basket.json when frozen)
    cost_pre, cost_now, items = food_kroger.basket_at(products, now_prices)
    foods = [dict(key=it["key"], name=it["name"], lbs=it["lbs_week"], n=it["n_products"],
                  avg_pre=it["price_lb_prewar"], avg_now=it["price_lb_now"], pct=it["pct"] / 100.0,
                  cost_pre=it["cost_week_prewar"], cost_now=it["cost_week_now"], tfp_share=it["tfp_share"] or 0,
                  products=[dict(upc=p["upc"], name=p["name"], size=next((q.get("size") for q in prod_by_key[it["key"]]["products"] if q["upc"] == p["upc"]), None),
                                 pre_reg=p["pre_regular"], now_reg=p["now_regular"], pre_lb=p["pre_lb"], now_lb=p["now_lb"],
                                 baseline_date=p["baseline_date"], early_war=p["early_war"], now_promo=p["now_promo"])
                            for p in it["products"]])
             for it in items]
    pct = cost_now / cost_pre - 1
    covered_share = sum(f["tfp_share"] for f in foods)
    base_dates = sorted(p["baseline_date"] for f in foods for p in f["products"] if p["pre_lb"] is not None)
    n_products = sum(f["n"] for f in foods)
    early = sum(1 for f in foods for p in f["products"] if p["early_war"] and p["pre_lb"] is not None)

    war = WAR_START
    months = months_between(war, now_date)
    monthly_spend = CEX_FOOD_AT_HOME_ANNUAL / 12.0
    trend = site["food"]["prewar_annual_trend_pct"] / 100.0
    drift = (1 + trend) ** (months / 12.0) - 1
    raw_monthly_now = pct * monthly_spend
    adj_monthly_now = (pct - drift) * monthly_spend
    cum_flat, cum_ramp = pct * monthly_spend * months, 0.5 * pct * monthly_spend * months
    cum_adj_flat, cum_adj_ramp = (pct - drift) * monthly_spend * months, 0.5 * (pct - drift) * monthly_spend * months

    # BLS cross-check, Feb 2026 -> latest month
    series = [s for k, (s, _) in BLS_MATCH.items() if k in {f["key"] for f in foods}]
    bls = fetch_bls.bls_series(series, 2026, 2026)
    xcheck = []
    for f in foods:
        if f["key"] not in BLS_MATCH:
            continue
        sid, label = BLS_MATCH[f["key"]]
        pts = bls.get(sid, {})
        feb = pts.get((2026, 2))
        if not pts or not feb:
            continue
        latest = max(pts)
        xcheck.append(dict(name=f["name"], label=label, kroger=f["pct"], bls=pts[latest] / feb - 1, month="%04d-%02d" % latest))

    L = []
    L.append("# Kroger basket test: a real basket of Thrifty Food Plan foods, before the war and now\n")
    stores = products.get("stores", {})
    n_by_store = {}
    for f in foods:
        for p in f["products"]:
            if p["pre_lb"] is not None:
                loc = next((q["location_id"] for q in prod_by_key[f["key"]]["products"] if q["upc"] == p["upc"]), "?")
                n_by_store[loc] = n_by_store.get(loc, 0) + 1
    L.append("Generated %s from `analysis/kroger/compare.py`. Stores: %s. Each product is priced at the store its "
             "pre-war page was archived from. Current prices: %s (%s). Pre-war prices: Wayback Machine snapshots of "
             "kroger.com product pages, %s to %s.\n" % (
                 date.today().isoformat(),
                 "; ".join("%s (%d products)" % (stores.get(k, k), v) for k, v in sorted(n_by_store.items())),
                 now["date"], now.get("source", "snapshot"), base_dates[0], base_dates[-1]))
    L.append("## Headline\n")
    L.append("| | Pre-war | Now (%s) | Change |" % now["date"])
    L.append("|---|---|---|---|")
    L.append("| Basket, reference family of four, per week | $%.2f | $%.2f | %s ($%+.2f) |" % (cost_pre, cost_now, fmt_pct(pct), cost_now - cost_pre))
    L.append("| Same change on the average household's food-at-home spend ($%.0f/mo) | | | $%+.2f per month |" % (monthly_spend, raw_monthly_now))
    L.append("| Trend-adjusted (prewar food trend %.2f%%/yr, %.1f months of drift = %s) | | | $%+.2f per month |" % (trend * 100, months, fmt_pct(drift), adj_monthly_now))
    L.append("| Cumulative since Feb 27, raw (ramp to flat) | | | $%+.0f to $%+.0f |" % (cum_ramp, cum_flat))
    L.append("| Cumulative since Feb 27, trend-adjusted (ramp to flat) | | | $%+.0f to $%+.0f |" % (cum_adj_ramp, cum_adj_flat))
    L.append("| Site's CPI method, cumulative food cost | | | $%+.2f |" % site["costs"]["food"])
    L.append("| CPI food at home since Feb 2026 | | | %s |\n" % fmt_pct(site["food"]["since_feb_pct"] / 100))
    L.append("Basket covers %d of %d foods, %d products, %.0f%% of the TFP reference-family dollars. "
             "%d product baselines are early-war snapshots (Feb 27 to Mar 13) rather than pre-war.\n"
             % (len(foods), len(basket["foods"]), n_products, covered_share * 100, early))

    L.append("## By food\n")
    L.append("| Food | lb/wk | n | $/lb pre-war | $/lb now | Change | $/wk pre-war | $/wk now |")
    L.append("|---|---|---|---|---|---|---|---|")
    for f in sorted(foods, key=lambda f: -f["cost_pre"]):
        L.append("| %s | %.2f | %d | $%.3f | $%.3f | %s | $%.2f | $%.2f |" % (f["name"], f["lbs"], f["n"], f["avg_pre"], f["avg_now"], fmt_pct(f["pct"]), f["cost_pre"], f["cost_now"]))
    L.append("")

    L.append("## Cross-check against BLS average prices (national, unadjusted)\n")
    L.append("| Food | Kroger change | BLS series | BLS change Feb 2026 to latest month with data |")
    L.append("|---|---|---|---|")
    for x in xcheck:
        L.append("| %s | %s | %s | %s (%s) |" % (x["name"], fmt_pct(x["kroger"]), x["label"], fmt_pct(x["bls"]), x["month"]))
    L.append("")

    L.append("## Products\n")
    L.append("| Food | UPC | Product | Size | Pre-war | Baseline date | Now | Now promo | $/lb pre | $/lb now |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for f in foods:
        for p in f["products"]:
            L.append("| %s | %s | %s | %s | %s | %s%s | %s | %s | %s | %s |" % (
                f["name"], p["upc"], (p["name"] or "")[:60], p["size"] or "",
                "$%.2f" % p["pre_reg"] if p["pre_reg"] is not None else "", p["baseline_date"], " (early war)" if p["early_war"] else "",
                "$%.2f" % p["now_reg"] if p["now_reg"] is not None else "no price",
                "$%.2f" % p["now_promo"] if p["now_promo"] else "",
                "$%.3f" % p["pre_lb"] if p["pre_lb"] is not None else "", "$%.3f" % p["now_lb"] if p["now_lb"] is not None else ""))
    L.append("")

    L.append("## Method and caveats\n")
    L.append("- Foods and quantities: the USDA Thrifty Food Plan, 2021 disaggregated market basket for the reference family "
             "(two adults 20-50, children 6-8 and 9-11). The %d costliest foods by weekly cost were kept; near-duplicates "
             "sold as one shelf product were merged. Pounds per week are the TFP quantities." % len(basket["foods"]))
    L.append("- Each food is priced as the simple average of up to three products' price per pound (Kroger label, a "
             "national brand, and one more). The same UPCs are priced at both dates. Fewer than three means the "
             "archive had no priced pre-war page for more candidates.")
    L.append("- Prices are the regular shelf price, not promotions, at both dates. Promo prices now are listed for reference.")
    L.append("- Pre-war prices come from archived kroger.com product pages (Wayback Machine), which embed the price for "
             "the crawler's default store. The archive date for each product is listed; a January price is a weaker "
             "baseline than a late-February one.")
    L.append("- Two stores in Virginia, both Kroger Mid-Atlantic. This is a store-level check of the national CPI number, not a replacement for it.")
    L.append("- The BLS cross-check uses each series' latest 2026 month; a month earlier than August means BLS has not published that item since.")
    L.append("- Sizes: milk at %.1f lb per gallon, juice and soy milk at %.4f lb per fl oz, large eggs at %.2f lb per dozen. "
             "Canned beans and corn use net can weight where the TFP quantity is cooked weight; quinoa uses dry weight."
             % (basket["lb_per_gallon_milk"], basket["lb_per_fl_oz_juice"], basket["lb_per_dozen_eggs"]))
    L.append("- Household scaling multiplies the basket's percent change by CEX 2024 food-at-home spending, the same "
             "spend the site's CPI method uses. Cumulative dollars are a range because there are only two price "
             "points: a linear ramp from zero at Feb 27 (low) or the full change from day one (high).")
    with open(OUT, "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:14]))
    print("wrote", OUT)


if __name__ == "__main__":
    sys.exit(main())
