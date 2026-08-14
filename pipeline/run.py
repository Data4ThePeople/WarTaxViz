"""Fetch everything, compute the War Tax numbers, write site/data.json, and
inline the JSON into site/index.html (from site/template.html)."""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

import compute
import fetch_aaa
import fetch_bls
import fetch_dfa
import fetch_eia
import fetch_fred
from constants import (BASKET_SERIES, CEX_ELECTRICITY_ANNUAL, CEX_FOOD_AT_HOME_ANNUAL,
                       CEX_GASOLINE_ANNUAL, CEX_NATURAL_GAS_ANNUAL, CPI_SERIES,
                       EIA_DIESEL_SERIES, GAS_AREAS, SCF_MEDIAN_DIRECT_STOCK_HOLDERS,
                       SCF_PCT_FAMILIES_DIRECT_STOCK, SEASONAL_YEARS, SP500_BASE_DATE,
                       SP500_BASE_EXPECTED, STATE_NAMES, STATE_TO_AREA, TAX_RATES,
                       WAR_START, gas_series_for_area)


def get_gas_weekly():
    start = date(SEASONAL_YEARS[0], 1, 1)
    try:
        weekly = fetch_eia.gas_weekly(start)
        source = "EIA API v2 (%s)" % "EMM_EPMR_PTE_NUS_DPG"
    except Exception as e:
        print("EIA fetch failed (%s); falling back to FRED GASREGW" % e)
        weekly = fetch_fred.gas_weekly(start)
        source = "FRED GASREGW (EIA mirror)"
    return weekly, source


def get_diesel_weekly():
    start = date(SEASONAL_YEARS[0], 1, 1)
    try:
        return fetch_eia.series_weekly(EIA_DIESEL_SERIES, start)
    except Exception as e:
        print("EIA diesel fetch failed (%s); falling back to FRED GASDESW" % e)
        return fetch_fred.fred_series("GASDESW", start)


def main():
    print("Fetching weekly gasoline...")
    gas_weekly, gas_source = get_gas_weekly()

    print("Fetching regional gasoline (9 states + 7 PADD districts)...")
    area_weekly = {}
    for area in GAS_AREAS:
        try:
            area_weekly[area] = fetch_eia.series_weekly(
                gas_series_for_area(area), date(SEASONAL_YEARS[0], 1, 1))
        except Exception as e:
            print("  %s failed (%s) — state picker will omit it" % (area, e))

    print("Fetching weekly diesel...")
    diesel_weekly = get_diesel_weekly()

    print("Fetching S&P 500...")
    sp500 = fetch_fred.sp500_daily(date(2026, 2, 20))

    print("Fetching BLS CPI + basket...")
    series_ids = list(CPI_SERIES.values()) + [s[0] for s in BASKET_SERIES]
    bls = fetch_bls.bls_series(series_ids, 2025, 2026)

    print("Fetching Fed DFA...")
    dfa_quarter, dfa = fetch_dfa.dfa_equity_by_group()

    print("Fetching AAA headline + state table...")
    aaa = fetch_aaa.aaa_national_average()
    aaa_states = fetch_aaa.aaa_state_averages() or {}

    # --- Gasoline (national) ---
    avg_2024 = [p for d, p in gas_weekly if d.year == 2024]
    avg_2024_price = sum(avg_2024) / len(avg_2024)
    gallons_per_year = CEX_GASOLINE_ANNUAL / avg_2024_price
    gallons_per_week = gallons_per_year / 52.0
    curve = compute.seasonal_curve(gas_weekly, SEASONAL_YEARS)
    gas = compute.gas_war_cost(gas_weekly, WAR_START, curve, gallons_per_week)
    gas["gallons_per_month"] = round(gallons_per_year / 12, 1)
    gas["aaa_latest"] = aaa
    gas["source"] = gas_source

    # --- Gasoline by region: each area gets its own seasonal curve + baseline.
    # Consumption is held at the national CEX-derived average.
    gas_regions = {"NUS": dict(gas, label="US average")}
    for area, weekly in area_weekly.items():
        try:
            a_curve = compute.seasonal_curve(weekly, SEASONAL_YEARS)
            region = compute.gas_war_cost(weekly, WAR_START, a_curve, gallons_per_week)
            region["label"] = GAS_AREAS[area]
            gas_regions[area] = region
        except Exception as e:
            print("  %s compute failed (%s)" % (area, e))
    states = {}
    for code, area in sorted(STATE_TO_AREA.items()):
        if area not in gas_regions:
            area = "NUS"
        states[code] = {"name": STATE_NAMES[code], "area": area,
                        "aaa": aaa_states.get(code)}

    # --- Diesel: same counterfactual, no direct household cost (it reaches
    # households through freight -> grocery prices, with a lag).
    d_curve = compute.seasonal_curve(diesel_weekly, SEASONAL_YEARS)
    diesel = compute.gas_war_cost(diesel_weekly, WAR_START, d_curve, 0.0)
    del diesel["total"]
    d_last = diesel["series"][-1]
    diesel["since_war_pct"] = round((diesel["latest_price"] / diesel["baseline_price"] - 1) * 100, 1)
    diesel["vs_cf_pct"] = round((d_last["actual"] / d_last["counterfactual"] - 1) * 100, 1)

    # --- Food & home energy (seasonally adjusted CPI vs pre-war trend) ---
    food = compute.cpi_war_cost(bls[CPI_SERIES["food_sa"]],
                                CEX_FOOD_AT_HOME_ANNUAL / 12)
    elec = compute.cpi_war_cost(bls[CPI_SERIES["electricity_sa"]],
                                CEX_ELECTRICITY_ANNUAL / 12)
    util_gas = compute.cpi_war_cost(bls[CPI_SERIES["gas_utility_sa"]],
                                    CEX_NATURAL_GAS_ANNUAL / 12)
    energy_total = elec["total"] + util_gas["total"]

    # --- Market ---
    market = compute.market_gain(sp500, SP500_BASE_DATE, SP500_BASE_EXPECTED)

    # --- Grocery basket display ---
    basket = []
    for sid, name, unit in BASKET_SERIES:
        pts = bls[sid]
        latest_ym = max(pts)
        basket.append({"name": name, "unit": unit,
                       "feb": pts.get((2026, 2)), "latest": pts[latest_ym],
                       "latest_month": "%04d-%02d" % latest_ym})

    # --- Personas from DFA (equities per household within each group) ---
    top01 = dfa["TopPt1"]
    top1_eq = top01["equities_musd"] + dfa["RemainingTop1"]["equities_musd"]
    top1_hh = top01["households"] + dfa["RemainingTop1"]["households"]
    personas = {
        "median": {
            "label": "Median American",
            "invested": 0,
            "tax": TAX_RATES["median"],
            "note": ("The median family holds $0 in stocks outside retirement "
                     "accounts (only %d%% hold any directly; median among holders "
                     "$%s). Fed SCF 2022."
                     % (round(SCF_PCT_FAMILIES_DIRECT_STOCK * 100),
                        format(int(SCF_MEDIAN_DIRECT_STOCK_HOLDERS), ",d"))),
        },
        "top1": {
            "label": "Top 1%",
            "invested": round(top1_eq * 1e6 / top1_hh),
            "group_equities_usd": round(top1_eq * 1e6),
            "group_households": round(top1_hh),
            "tax": TAX_RATES["top1"],
            "note": ("Average equities & mutual fund holdings per top-1%% "
                     "household — excludes pensions and 401(k)s (IRAs can't be "
                     "separated out). Fed DFA, %s." % dfa_quarter),
        },
        "top01": {
            "label": "Top 0.1%",
            "invested": round(top01["equities_musd"] * 1e6 / top01["households"]),
            "group_equities_usd": round(top01["equities_musd"] * 1e6),
            "group_households": round(top01["households"]),
            "tax": TAX_RATES["top01"],
            "note": ("Average equities & mutual fund holdings per top-0.1%% "
                     "household — excludes pensions and 401(k)s (IRAs can't be "
                     "separated out). Fed DFA, %s." % dfa_quarter),
        },
    }

    data = {
        "war_start": WAR_START.isoformat(),
        "generated": date.today().isoformat(),
        "costs": {
            "gas": round(gas["total"], 2),
            "food": round(food["total"], 2),
            "energy": round(energy_total, 2),
            "total": round(gas["total"] + food["total"] + energy_total, 2),
        },
        "gas": gas,
        "gas_regions": gas_regions,
        "states": states,
        "diesel": diesel,
        "food": food,
        "electricity": elec,
        "utility_gas": util_gas,
        "market": market,
        "basket": basket,
        "personas": personas,
        "default_tax": TAX_RATES["you"],
        "dfa_quarter": dfa_quarter,
    }

    out_json = os.path.join(ROOT, "site", "data.json")
    with open(out_json, "w") as f:
        json.dump(data, f, indent=1)
    print("Wrote %s" % out_json)

    for tpl_name, out_name in [("template.html", "index.html"),
                               ("embed-template.html", "embed.html")]:
        template = os.path.join(ROOT, "site", tpl_name)
        if not os.path.exists(template):
            continue
        with open(template) as f:
            html = f.read()
        html = html.replace("__DATA_JSON__", json.dumps(data))
        out_html = os.path.join(ROOT, "site", out_name)
        with open(out_html, "w") as f:
            f.write(html)
        print("Wrote %s" % out_html)

    # Summary for eyeballing
    total_cost = data["costs"]["total"]
    gain = market["gain_pct"]
    print("\n=== War Tax summary (as of %s) ===" % market["latest_date"])
    print("Gas: $%.2f  Food: $%.2f  Energy: $%.2f  TOTAL COST: $%.2f"
          % (gas["total"], food["total"], energy_total, total_cost))
    print("S&P: %.2f -> %.2f  (%+.2f%%)" % (market["base"], market["latest"],
                                            gain * 100))
    for k, p in personas.items():
        net = p["invested"] * gain * (1 - p["tax"]) - total_cost
        print("%-8s invested $%s -> net $%s"
              % (k, format(p["invested"], ",d"), format(round(net), ",d")))
    breakeven = total_cost / (gain * (1 - TAX_RATES["you"]))
    print("Breakeven at 22%% tax: $%s invested on %s"
          % (format(round(breakeven), ",d"), WAR_START))


if __name__ == "__main__":
    main()
