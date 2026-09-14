"""Food-at-home cost from the fixed Kroger basket (the alternative to the CPI method).

Inputs are the frozen product list (data/kroger/products.json, with each product's
pre-war baseline price) and the weekly price snapshots (data/kroger/snapshots/*.json).
The basket index is basket cost now / basket cost pre-war, with the same quantity weights
(TFP pounds per week) at both dates. The cost accounting mirrors compute.cpi_war_cost:
the prewar food trend continues as the counterfactual, and the household pays the
excess of the basket index over that path, on CEX food-at-home spending, integrated
over the actual snapshot dates (index 1.0 on the war's first day, linear between
snapshots).
"""

import glob
import json
import os
from datetime import date

from units import unit_price_per_lb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(ROOT, "data", "kroger", "products.json")
SNAPSHOTS = os.path.join(ROOT, "data", "kroger", "snapshots")


def load_inputs():
    """(products, [snapshots sorted by date]) or (None, []) when the experiment has no data yet."""
    if not os.path.exists(PRODUCTS):
        return None, []
    products = json.load(open(PRODUCTS))
    snaps = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(SNAPSHOTS, "*.json")))]
    snaps = [s for s in snaps if s.get("prices")]
    return products, sorted(snaps, key=lambda s: s["date"])


def price_food(food, prices):
    """Average $/lb across the food's products, pre-war and at one snapshot.

    prices: {upc: {regular, size, sold_by/sell_by, promo}} for the snapshot.
    Only products priced at both dates count, so the pair is always like for like."""
    pre_list, now_list, rows = [], [], []
    for p in food["products"]:
        base = p["baseline"]
        pre = unit_price_per_lb(base.get("regular"), p.get("size"), food["key"], p.get("sell_by"), p.get("weight_lb"))
        cur = prices.get(p["upc"]) or {}
        now = unit_price_per_lb(cur.get("regular"), cur.get("size") or p.get("size"), food["key"],
                                cur.get("sold_by") or cur.get("sell_by") or p.get("sell_by"), p.get("weight_lb"))
        rows.append(dict(upc=p["upc"], name=p.get("name"), pre_lb=pre, now_lb=now,
                         pre_regular=base.get("regular"), now_regular=cur.get("regular"), now_promo=cur.get("promo"),
                         baseline_date=(base.get("ts") or "")[:8], early_war=bool(base.get("early_war"))))
        if pre is not None and now is not None:
            pre_list.append(pre)
            now_list.append(now)
    if not pre_list:
        return None
    n = len(pre_list)
    return dict(n=n, avg_pre=sum(pre_list) / n, avg_now=sum(now_list) / n, products=rows)


def basket_at(products, prices):
    """Basket cost per week pre-war and at one snapshot, plus per-food detail."""
    items, cost_pre, cost_now = [], 0.0, 0.0
    for food in products["foods"]:
        r = price_food(food, prices)
        if r is None:
            continue
        lbs = food["lbs_week"]
        cost_pre += lbs * r["avg_pre"]
        cost_now += lbs * r["avg_now"]
        items.append(dict(key=food["key"], name=food["name"], lbs_week=lbs, n_products=r["n"],
                          price_lb_prewar=round(r["avg_pre"], 4), price_lb_now=round(r["avg_now"], 4),
                          pct=round((r["avg_now"] / r["avg_pre"] - 1) * 100, 2),
                          cost_week_prewar=round(lbs * r["avg_pre"], 2), cost_week_now=round(lbs * r["avg_now"], 2),
                          tfp_share=food.get("tfp_share"), products=r["products"]))
    return cost_pre, cost_now, items


def kroger_food_cost(products, snapshots, monthly_spend, annual_trend_pct, war_start):
    """Same shape of result as compute.cpi_war_cost, built from the basket snapshots."""
    if not products or not snapshots:
        return None
    monthly_trend = (1 + annual_trend_pct / 100.0) ** (1.0 / 12) - 1
    # index path: (months since war start, basket index); starts at (0, 1.0)
    path = [(0.0, 1.0, None)]
    series = []
    last_items = None
    for snap in snapshots:
        d = date.fromisoformat(snap["date"])
        cost_pre, cost_now, items = basket_at(products, snap["prices"])
        if cost_pre <= 0:
            continue
        idx = cost_now / cost_pre
        t = (d - war_start).days / 30.4375
        path.append((t, idx, snap))
        last_items = (cost_pre, cost_now, items, snap)
        cf = (1 + monthly_trend) ** t
        series.append({"date": snap["date"], "index": round(idx, 5), "counterfactual": round(cf, 5),
                       "excess_pct": round((idx / cf - 1) * 100, 2), "basket_prewar": round(cost_pre, 2),
                       "basket_now": round(cost_now, 2), "n_foods": len(items)})
    if last_items is None:
        return None
    # integrate the excess rate (index/cf - 1) * monthly_spend over months, trapezoid between points
    total = 0.0
    for (t0, i0, _), (t1, i1, _) in zip(path, path[1:]):
        r0 = (i0 / (1 + monthly_trend) ** t0 - 1) * monthly_spend
        r1 = (i1 / (1 + monthly_trend) ** t1 - 1) * monthly_spend
        total += 0.5 * (r0 + r1) * (t1 - t0)
    cost_pre, cost_now, items, snap = last_items
    base_dates = sorted(p["baseline_date"] for it in items for p in it["products"] if p["pre_lb"] is not None and p["baseline_date"])
    early = sum(1 for it in items for p in it["products"] if p["early_war"] and p["pre_lb"] is not None)
    return {
        "total": total,
        "series": series,
        "prewar_annual_trend_pct": annual_trend_pct,
        "since_prewar_pct": round((cost_now / cost_pre - 1) * 100, 2),
        "basket_prewar": round(cost_pre, 2),
        "basket_now": round(cost_now, 2),
        "as_of": snap["date"],
        "baseline_dates": [base_dates[0], base_dates[-1]] if base_dates else None,
        "early_war_baselines": early,
        "store": products.get("store"),
        "n_foods": len(items),
        "n_products": sum(it["n_products"] for it in items),
        "coverage_share": round(sum(it["tfp_share"] or 0 for it in items), 4),
        "monthly_spend": monthly_spend,
        "items": [{k: v for k, v in it.items() if k != "products"} for it in items],
    }
