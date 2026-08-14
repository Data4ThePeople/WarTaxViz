"""War Tax math: seasonal gas counterfactual, CPI trend counterfactuals, market gain.

All costs = actual minus projected no-war path, accumulated from the war start.
"""

from collections import defaultdict
from statistics import median


def seasonal_curve(weekly, years):
    """Median seasonal ratio by weeks-elapsed-since-late-February.

    For each historical year: ratio = price / (last February weekly print of that
    year), keyed by whole weeks since that print. The cross-year median is robust
    to the 2020 COVID crash and 2022 Ukraine spike without hand-picked exclusions.
    """
    by_year = defaultdict(list)
    for d, p in weekly:
        by_year[d.year].append((d, p))
    ratios = defaultdict(list)
    for y in years:
        obs = sorted(by_year.get(y, []))
        feb = [o for o in obs if o[0].month == 2]
        if not feb:
            continue
        base_date, base_price = feb[-1]
        for d, p in obs:
            if d >= base_date:
                ratios[(d - base_date).days // 7].append(p / base_price)
    return {wk: median(v) for wk, v in ratios.items()}


def gas_war_cost(weekly, war_start, curve, gallons_per_week):
    """Cumulative excess gasoline cost + the actual-vs-counterfactual series."""
    obs = sorted((d, p) for d, p in weekly if d.year == war_start.year)
    pre_war = [(d, p) for d, p in obs if d < war_start]
    base_date, base_price = pre_war[-1]  # last weekly print before the war
    max_wk = max(curve)
    series, total = [], 0.0
    for d, p in obs:
        if d < base_date:
            continue
        wk = (d - base_date).days // 7
        cf = base_price * curve.get(wk, curve[max_wk])
        series.append({"date": d.isoformat(), "actual": round(p, 3),
                       "counterfactual": round(cf, 3)})
        if d >= war_start:
            total += (p - cf) * gallons_per_week
    peak_date, peak_price = max(obs, key=lambda o: o[1])
    return {
        "total": total,
        "series": series,
        "baseline_date": base_date.isoformat(),
        "baseline_price": base_price,
        "latest_date": obs[-1][0].isoformat(),
        "latest_price": obs[-1][1],
        "peak_date": peak_date.isoformat(),
        "peak_price": peak_price,
    }


def cpi_war_cost(points, monthly_spend, base_ym=(2026, 2)):
    """Cumulative excess cost for one CPI category (seasonally adjusted index).

    Counterfactual: the pre-war trailing-12-month inflation rate continues from the
    February 2026 index. (Feb-to-Feb year-over-year cleanly straddles the Oct 2025
    shutdown data hole.)
    """
    base = points[base_ym]
    prior = points[(base_ym[0] - 1, base_ym[1])]
    monthly_trend = (base / prior) ** (1.0 / 12) - 1
    months = sorted(k for k in points if k > base_ym)
    series, total = [], 0.0
    for i, ym in enumerate(months, start=1):
        cf = base * (1 + monthly_trend) ** i
        excess_frac = points[ym] / cf - 1
        cost = excess_frac * monthly_spend
        total += cost
        series.append({"month": "%04d-%02d" % ym, "index": points[ym],
                       "counterfactual": round(cf, 3),
                       "excess_pct": round(excess_frac * 100, 2),
                       "cost": round(cost, 2)})
    return {
        "total": total,
        "series": series,
        "prewar_annual_trend_pct": round((base / prior - 1) * 100, 2),
        "since_feb_pct": round((points[months[-1]] / base - 1) * 100, 2),
        "latest_month": "%04d-%02d" % months[-1],
        "monthly_spend": monthly_spend,
    }


def market_gain(daily, base_date, expected_base=None, tolerance=0.5):
    closes = dict(daily)
    base = closes.get(base_date)
    if base is None:
        raise RuntimeError("No S&P close for %s" % base_date)
    if expected_base and abs(base - expected_base) > tolerance:
        raise RuntimeError("S&P base %.2f != expected %.2f" % (base, expected_base))
    latest_date, latest = sorted(daily)[-1]
    return {
        "base_date": base_date.isoformat(),
        "base": base,
        "latest_date": latest_date.isoformat(),
        "latest": latest,
        "gain_pct": latest / base - 1,
        "series": [{"date": d.isoformat(), "close": c} for d, c in sorted(daily)],
    }
